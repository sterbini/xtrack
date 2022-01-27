
import json
import numpy as np

import xobjects as xo
import xtrack as xt
import xpart as xp

###############
# Load a line #
###############

fname_line_particles = '../../test_data/hllhc15_noerrors_nobb/line_and_particle.json'
#fname_line_particles = '../../test_data/sps_w_spacecharge/line_no_spacecharge_and_particle.json' #!skip-doc

with open(fname_line_particles, 'r') as fid:
    input_data = json.load(fid)
line = xt.Line.from_dict(input_data['line'])
particle_ref = xp.Particles.from_dict(input_data['particle'])

#################
# Build tracker #
#################

tracker = xt.Tracker(line=line)
