// ##################################
// Beam Size Monitor
// 
// Author: Philipp Niedermayer
// Date: 2023-08-14
// ##################################


#ifndef XTRACK_BEAM_SIZE_MONITOR_H
#define XTRACK_BEAM_SIZE_MONITOR_H

#if !defined( C_LIGHT )
    #define   C_LIGHT ( 299792458.0 )
#endif /* !defined( C_LIGHT ) */


#pragma OPENCL EXTENSION cl_khr_fp64: enable                                                      //only_for_context opencl
#pragma OPENCL EXTENSION cl_khr_int64_base_atomics: enable                                        //only_for_context opencl
/*gpufun*/                                                                                        //only_for_context opencl
void atomic_add_d(__global double *val, double delta) {                                           //only_for_context opencl
  union {                                                                                         //only_for_context opencl
    double f;                                                                                     //only_for_context opencl
    ulong  i;                                                                                     //only_for_context opencl
  } read, write;                                                                                  //only_for_context opencl
  do {                                                                                            //only_for_context opencl
    read.f = *val;                                                                                //only_for_context opencl
    write.f = read.f + delta;                                                                     //only_for_context opencl
  } while (atom_cmpxchg ( (volatile __global ulong *)val, read.i, write.i) != read.i);            //only_for_context opencl
}                                                                                                 //only_for_context opencl


/*gpufun*/
void BeamSizeMonitor_track_local_particle(BeamSizeMonitorData el, LocalParticle* part0){

    // get parameters
    int64_t const start_at_turn = BeamSizeMonitorData_get_start_at_turn(el);
    int64_t particle_id_start = BeamSizeMonitorData_get_particle_id_start(el);
    int64_t particle_id_stop = particle_id_start + BeamSizeMonitorData_get_num_particles(el);
    double const frev = BeamSizeMonitorData_get_frev(el);
    double const sampling_frequency = BeamSizeMonitorData_get_sampling_frequency(el);
    
    BeamSizeMonitorRecord record = BeamSizeMonitorData_getp_data(el);                 //only_for_context cpu_serial cpu_openmp
    /*gpuglmem*/ BeamSizeMonitorRecord * record = BeamSizeMonitorData_getp_data(el);  //only_for_context opencl cuda
    
    int64_t max_slot = BeamSizeMonitorRecord_len_count(record);


    //start_per_particle_block(part0->part)

        int64_t particle_id = LocalParticle_get_particle_id(part);
        if (particle_id_stop < 0 || (particle_id_start <= particle_id && particle_id < particle_id_stop)){

            // zeta is the absolute path length deviation from the reference particle: zeta = (s - beta0*c*t)
            // but without limits, i.e. it can exceed the circumference (for coasting beams)
            // as the particle falls behind or overtakes the reference particle
            double const zeta = LocalParticle_get_zeta(part);
            double const at_turn = LocalParticle_get_at_turn(part);
            double const beta0 = LocalParticle_get_beta0(part);

            // compute sample index
            int64_t slot = round(sampling_frequency * ( (at_turn-start_at_turn)/frev - zeta/beta0/C_LIGHT ));

            if (slot >= 0 && slot < max_slot){
                double x = LocalParticle_get_x(part);
                double y = LocalParticle_get_y(part);
                
                /*gpuglmem*/ int64_t * count = BeamSizeMonitorRecord_getp1_count(record, slot);
                #pragma omp atomic capture    //only_for_context cpu_openmp
                (*count) += 1;                //only_for_context cpu_serial cpu_openmp
                atomic_add(count, 1);         //only_for_context opencl
                atomicAdd(count, 1);          //only_for_context cuda
                
                /*gpuglmem*/ double * x_sum = BeamSizeMonitorRecord_getp1_x_sum(record, slot);
                #pragma omp atomic capture    //only_for_context cpu_openmp
                (*x_sum) += x;                //only_for_context cpu_serial cpu_openmp
                atomic_add_d(x_sum, x);       //only_for_context opencl
                atomicAdd(x_sum, x);          //only_for_context cuda
                
                /*gpuglmem*/ double * y_sum = BeamSizeMonitorRecord_getp1_y_sum(record, slot);
                #pragma omp atomic capture    //only_for_context cpu_openmp
                (*y_sum) += y;                //only_for_context cpu_serial cpu_openmp
                atomic_add_d(y_sum, y);       //only_for_context opencl
                atomicAdd(y_sum, y);          //only_for_context cuda
                
                /*gpuglmem*/ double * x2_sum = BeamSizeMonitorRecord_getp1_x2_sum(record, slot);
                #pragma omp atomic capture    //only_for_context cpu_openmp
                (*x2_sum) += x*x;             //only_for_context cpu_serial cpu_openmp
                atomic_add_d(x2_sum, x*x);    //only_for_context opencl
                atomicAdd(x2_sum, x*x);       //only_for_context cuda
                
                /*gpuglmem*/ double * y2_sum = BeamSizeMonitorRecord_getp1_y2_sum(record, slot);
                #pragma omp atomic capture    //only_for_context cpu_openmp
                (*y2_sum) += y*y;             //only_for_context cpu_serial cpu_openmp
                atomic_add_d(y2_sum, y*y);    //only_for_context opencl
                atomicAdd(y2_sum, y*y);       //only_for_context cuda
                
            }

        }

	//end_per_particle_block

}

#endif

