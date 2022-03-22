from cpymad.madx import Madx
import xpart as xp
import xobjects as xo
import xtrack as xt
import xfields as xf
import numpy as np
xp.enable_pyheadtail_interface()

gpu_device = 0

seq_name = "sps"


qx0,qy0 = 20.13, 20.18
p0c = 26e9
cavity_name = "actcse.31632"
cavity_lag = 180
frequency = 200e6
rf_voltage = 4e6

use_wakes = True
n_slices_wakes = 100
limit_z = 0.7

bunch_intensity = 1* 1e11/3 # Need short bunch to avoid bucket non-linearity
                        # to compare frozen/quasi-frozen and PIC
sigma_z = 22.5e-2/3
nemitt_x=2.5e-6
nemitt_y=2.5e-6
n_part=int(1e2)
num_turns=2

num_spacecharge_interactions = 540
tol_spacecharge_position = 1e-2

mode = 'frozen' #
#mode = 'pic'
########


mad = Madx()
mad.call("./madx_sps/sps.seq")
mad.call("./madx_sps/lhc_q20.str")
mad.call("./madx_sps/macro.madx")

mad.beam()
mad.use(seq_name)

mad.twiss()
tw_thick = mad.table.twiss.dframe()
summ_thick = mad.table.summ.dframe()

mad.input("""select, flag=makethin, slice=1, thick=false;
            makethin, sequence=sps, style=teapot, makedipedge=false;""")
mad.use(seq_name)
mad.exec(f"sps_match_tunes({qx0},{qy0});")



####################
# Choose a context #
####################

if gpu_device is None:
   context = xo.ContextCpu()
else:
   context = xo.ContextCupy(device=gpu_device)


line = xt.Line.from_madx_sequence(sequence=mad.sequence[seq_name],
           deferred_expressions=True, install_apertures=True,
           apply_madx_errors=False)

line.particle_ref = xp.Particles(p0c=p0c,mass0=xp.PROTON_MASS_EV)
line[cavity_name].voltage = rf_voltage
line[cavity_name].lag = cavity_lag
line[cavity_name].frequency = frequency


tw = xt.Tracker(line=line.copy()).twiss()

#############################################
# Install spacecharge interactions (frozen) #
#############################################

lprofile = xf.LongitudinalProfileQGaussian(
       number_of_particles=bunch_intensity,
       sigma_z=sigma_z,
       z0=0.,
       q_parameter=1.)

xf.install_spacecharge_frozen(line=line,
                  particle_ref=line.particle_ref,
                  longitudinal_profile=lprofile,
                  nemitt_x=nemitt_x, nemitt_y=nemitt_y,
                  sigma_z=sigma_z,
                  num_spacecharge_interactions=num_spacecharge_interactions,
                  tol_spacecharge_position=tol_spacecharge_position)


#################################
# Switch to PIC or quasi-frozen #
#################################

if mode == 'frozen':
   pass # Already configured in line
elif mode == 'quasi-frozen':
   xf.replace_spacecharge_with_quasi_frozen(
                                   line,
                                   update_mean_x_on_track=True,
                                   update_mean_y_on_track=True)
elif mode == 'pic':
   pic_collection, all_pics = xf.replace_spacecharge_with_PIC(
       _context=context, line=line,
       n_sigmas_range_pic_x=8,
       n_sigmas_range_pic_y=8,
       nx_grid=256, ny_grid=256, nz_grid=100,
       n_lims_x=7, n_lims_y=3,
       z_range=(-3*sigma_z, 3*sigma_z))
else:
   raise ValueError(f'Invalid mode: {mode}')


if use_wakes:
   ##############################
   # # install wakefields #######
   wakefields = np.genfromtxt('wakes/kickerSPSwake_2020_oldMKP.wake')
   # # adapt to beta function at lattice start
   X_dip_factor = 54.65/tw['betx'][0]
   Y_dip_factor = 54.51/tw['bety'][0]
   X_quad_factor = 54.65/tw['betx'][0]
   Y_quad_factor = 54.51/tw['bety'][0]
   wakefields[:,1] *= X_dip_factor
   wakefields[:,2] *= Y_dip_factor
   wakefields[:,3] *= X_quad_factor
   wakefields[:,4] *= Y_quad_factor

   wakefile = 'wakes/wakefields.wake'
   np.savetxt(wakefile,wakefields,delimiter='\t')

   from PyHEADTAIL.particles.slicing import UniformBinSlicer
   from PyHEADTAIL.impedances.wakes import WakeTable, WakeField

   n_slices_wakes = 500 # 500
   slicer_for_wakefields = UniformBinSlicer(n_slices_wakes, z_cuts=(-limit_z, limit_z))

   waketable = WakeTable(wakefile, ['time', 'dipole_x', 'dipole_y', 'quadrupole_x', 'quadrupole_y']) #, n_turns_wake=n_turns_wake)
   wakefield = WakeField(slicer_for_wakefields, waketable)
   wakefield.needs_cpu = True
   wakefield.needs_hidden_lost_particles = True
   #line.append_element(element=wakefield,name="wakefield")
   line.insert_element(element=wakefield,name="wakefield", at_s=0)

   ###############################



#################
# Build Tracker #
#################

tracker = xt.Tracker(_context=context,
                   line=line)
tracker_sc_off = tracker.filter_elements(exclude_types_starting_with='SpaceCh')

######################
# Generate particles #
######################

# (we choose to match the distribution without accounting for spacecharge)
particles = xp.generate_matched_gaussian_bunch(_context=context,
        num_particles=n_part, total_intensity_particles=bunch_intensity,
        nemitt_x=nemitt_x, nemitt_y=nemitt_y, sigma_z=sigma_z,
        particle_ref=tracker.particle_ref, tracker=tracker_sc_off)
particles.circumference = line.get_length()



class PhaseMonitor:
   def __init__(self, tracker, num_particles, twiss):
       self.twiss = twiss
       self.phase_x = []
       self.phase_y = []
       self._monitor = xt.ParticlesMonitor(_context=tracker._buffer.context,
                                        num_particles=particles._capacity,
                                        start_at_turn=0,
                                        stop_at_turn=1)


   def measure(self, particles):
       self._monitor.track(particles)

       delta = self._monitor.delta
       tw = self.twiss

       for ss in 'xy':
           r = getattr(self._monitor, ss).copy()
           pr = getattr(self._monitor, f'p{ss}').copy()

           r -= delta*tw[f'd{ss}'][0]
           pr -= delta*tw[f'dp{ss}'][0]

           betr = tw[f'bet{ss}'][0]
           alfr = tw[f'alf{ss}'][0]

           phase = np.angle(r / np.sqrt(betr) -
                       1j*(r * alfr / np.sqrt(betr) +
                       pr * np.sqrt(betr)))

           getattr(self, f'phase_{ss}').append(
                              np.atleast_1d(np.squeeze(phase)))

       self._monitor.start_at_turn += 1
       self._monitor.stop_at_turn += 1

   @property
   def qx(self):
       return np.mod(np.diff(np.array(self.phase_x), axis=0)/(2*np.pi), 1)

   @property
   def qy(self):
       return np.mod(np.diff(np.array(self.phase_y), axis=0)/(2*np.pi), 1)

phasem = PhaseMonitor(tracker, num_particles=n_part, twiss=tw)

for turn in range(num_turns):
   phasem.measure(particles)
   #import pdb; pdb.set_trace()
   tracker.track(particles)

import matplotlib.pyplot as plt
plt.close('all')
plt.ion()
f,ax = plt.subplots()
ax.plot(phasem.qx, phasem.qy,'b.',ms=1)
ax.set_xlim(0, 0.5)
ax.set_ylim(0, 0.5)
plt.show()