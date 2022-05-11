from tkinter import W
import numpy as np

import xtrack as xt
import xpart as xp
import xobjects as xo

def test_record_single_table():
    class TestElementRecord(xo.DressedStruct):
        _xofields = {
            '_index': xt.RecordIndex,
            'generated_rr': xo.Float64[:],
            'at_element': xo.Int64[:],
            'at_turn': xo.Int64[:],
            'particle_id': xo.Int64[:]
            }

    class TestElement(xt.BeamElement):
        _xofields={
            'n_kicks': xo.Int64,
            }

        _internal_record_class = TestElementRecord

    TestElement.XoStruct.extra_sources.extend([
        xp._pkg_root.joinpath('random_number_generator/rng_src/base_rng.h'),
        xp._pkg_root.joinpath('random_number_generator/rng_src/local_particle_rng.h'),
        ])

    TestElement.XoStruct.extra_sources.append(r'''
        /*gpufun*/
        void TestElement_track_local_particle(TestElementData el, LocalParticle* part0){

            // Extract the record and record_index
            TestElementRecordData record = TestElementData_getp_internal_record(el, part0);
            RecordIndex record_index = NULL;
            if (record){
                record_index = TestElementRecordData_getp__index(record);
            }

            int64_t n_kicks = TestElementData_get_n_kicks(el);
            //printf("n_kicks %d\n", (int)n_kicks);

            //start_per_particle_block (part0->part)

                for (int64_t i = 0; i < n_kicks; i++) {
                    double rr = 1e-6 * LocalParticle_generate_random_double(part);
                    LocalParticle_add_to_px(part, rr);

                    if (record){
                        // Get a slot in the record (this is thread safe)
                        int64_t i_slot = RecordIndex_get_slot(record_index);
                        // The returned slot id is negative if record is NULL or if record is full

                        if (i_slot>=0){
                            TestElementRecordData_set_at_element(record, i_slot,
                                                        LocalParticle_get_at_element(part));
                            TestElementRecordData_set_at_turn(record, i_slot,
                                                        LocalParticle_get_at_turn(part));
                            TestElementRecordData_set_particle_id(record, i_slot,
                                                        LocalParticle_get_particle_id(part));
                            TestElementRecordData_set_generated_rr(record, i_slot, rr);
                        }
                    }
                }


            //end_per_particle_block
        }
        ''')

    for context in xo.context.get_test_contexts():
        print(f"Test {context.__class__}")
        n_kicks0 = 5
        n_kicks1 = 3
        tracker = xt.Tracker(_context=context, line=xt.Line(elements = [
            TestElement(n_kicks=n_kicks0), TestElement(n_kicks=n_kicks1)]))
        tracker.line._needs_rng = True

        record = tracker.start_internal_logging_for_elements_of_type(
                                                            TestElement, capacity=10000)

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        tracker.track(part, num_turns=num_turns0)
        tracker.track(part, num_turns=num_turns1)

        num_recorded = record._index.num_recorded
        num_turns = num_turns0 + num_turns1
        num_particles = len(part.x)
        part._move_to(_context=xo.ContextCpu())
        record._move_to(_context=xo.ContextCpu())
        assert num_recorded == (num_particles * num_turns * (n_kicks0 + n_kicks1))

        assert np.sum((record.at_element[:num_recorded] == 0)) == (num_particles * num_turns
                                                * n_kicks0)
        assert np.sum((record.at_element[:num_recorded] == 1)) == (num_particles * num_turns
                                                * n_kicks1)
        for i_turn in range(num_turns):
            assert np.sum((record.at_turn[:num_recorded] == i_turn)) == (num_particles
                                                                * (n_kicks0 + n_kicks1))

        # Check reached capacity
        record = tracker.start_internal_logging_for_elements_of_type(
                                                            TestElement, capacity=20)

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        tracker.track(part, num_turns=num_turns0)
        tracker.track(part, num_turns=num_turns1)

        num_recorded = record._index.num_recorded
        assert num_recorded == 20


        # Check stop
        record = tracker.start_internal_logging_for_elements_of_type(
                                                            TestElement, capacity=10000)

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        num_particles = len(part.x)
        tracker.track(part, num_turns=num_turns0)
        tracker.stop_internal_logging_for_elements_of_type(TestElement)
        tracker.track(part, num_turns=num_turns1)

        num_recorded = record._index.num_recorded
        num_turns = num_turns0
        part._move_to(_context=xo.ContextCpu())
        record._move_to(_context=xo.ContextCpu())
        assert np.all(part.at_turn == num_turns0 + num_turns1)
        assert num_recorded == (num_particles * num_turns
                                                * (n_kicks0 + n_kicks1))

        assert np.sum((record.at_element[:num_recorded] == 0)) == (num_particles * num_turns
                                                * n_kicks0)
        assert np.sum((record.at_element[:num_recorded] == 1)) == (num_particles * num_turns
                                                * n_kicks1)
        for i_turn in range(num_turns):
            assert np.sum((record.at_turn[:num_recorded] == i_turn)) == (num_particles
                                                                * (n_kicks0 + n_kicks1))

        # Collective
        n_kicks0 = 5
        n_kicks1 = 3
        elements = [
            TestElement(n_kicks=n_kicks0, _context=context), TestElement(n_kicks=n_kicks1)]
        elements[0].iscollective = True
        tracker = xt.Tracker(_context=context, line=xt.Line(elements=elements))
        tracker.line._needs_rng = True

        record = tracker.start_internal_logging_for_elements_of_type(
                                                            TestElement, capacity=10000)

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        tracker.track(part, num_turns=num_turns0)
        tracker.stop_internal_logging_for_elements_of_type(TestElement)
        tracker.track(part, num_turns=num_turns1)

        # Checks
        part._move_to(_context=xo.ContextCpu())
        record._move_to(_context=xo.ContextCpu())
        num_recorded = record._index.num_recorded
        num_turns = num_turns0
        num_particles = len(part.x)
        assert np.all(part.at_turn == num_turns0 + num_turns1)
        assert num_recorded == (num_particles * num_turns
                                                * (n_kicks0 + n_kicks1))

        assert np.sum((record.at_element[:num_recorded] == 0)) == (num_particles * num_turns
                                                * n_kicks0)
        assert np.sum((record.at_element[:num_recorded] == 1)) == (num_particles * num_turns
                                                * n_kicks1)
        for i_turn in range(num_turns):
            assert np.sum((record.at_turn[:num_recorded] == i_turn)) == (num_particles
                                                                * (n_kicks0 + n_kicks1))

def test_record_multiple_tables():

    class Table1(xo.DressedStruct):
        _xofields = {
            '_index': xt.RecordIndex,
            'particle_x': xo.Float64[:],
            'particle_px': xo.Float64[:],
            'at_element': xo.Int64[:],
            'at_turn': xo.Int64[:],
            'particle_id': xo.Int64[:]
            }

    class Table2(xo.DressedStruct):
        _xofields = {
            '_index': xt.RecordIndex,
            'generated_rr': xo.Float64[:],
            'at_element': xo.Int64[:],
            'at_turn': xo.Int64[:],
            'particle_id': xo.Int64[:]
            }

    class TestElementRecord(xo.DressedStruct):
        _xofields = {
            'table1': Table1.XoStruct,
            'table2': Table2.XoStruct
            }

    class TestElement(xt.BeamElement):
        _xofields={
            'n_kicks': xo.Int64,
            }
        _internal_record_class = TestElementRecord

    TestElement.XoStruct.extra_sources.extend([
        xp._pkg_root.joinpath('random_number_generator/rng_src/base_rng.h'),
        xp._pkg_root.joinpath('random_number_generator/rng_src/local_particle_rng.h'),
        ])

    TestElement.XoStruct.extra_sources.append(r'''
        /*gpufun*/
        void TestElement_track_local_particle(TestElementData el, LocalParticle* part0){

            // Extract the record and record_index
            TestElementRecordData record = TestElementData_getp_internal_record(el, part0);
            Table1Data table1 = NULL;
            Table2Data table2 = NULL;
            RecordIndex table1_index = NULL;
            RecordIndex table2_index = NULL;
            if (record){
                table1 = TestElementRecordData_getp_table1(record);
                table2 = TestElementRecordData_getp_table2(record);
                table1_index = Table1Data_getp__index(table1);
                table2_index = Table2Data_getp__index(table2);
            }

            int64_t n_kicks = TestElementData_get_n_kicks(el);
            // printf("n_kicks %d\n", (int)n_kicks);

            //start_per_particle_block (part0->part)

                // Record in table1 info about the ingoing particle
                if (record){
                    // Get a slot in table1
                    int64_t i_slot = RecordIndex_get_slot(table1_index);
                    // The returned slot id is negative if record is NULL or if record is full
                    // printf("i_slot %d\n", (int)i_slot);

                    if (i_slot>=0){
                            Table1Data_set_particle_x(table1, i_slot,
                                                        LocalParticle_get_x(part));
                            Table1Data_set_particle_px(table1, i_slot,
                                                        LocalParticle_get_px(part));
                            Table1Data_set_at_element(table1, i_slot,
                                                        LocalParticle_get_at_element(part));
                            Table1Data_set_at_turn(table1, i_slot,
                                                        LocalParticle_get_at_turn(part));
                            Table1Data_set_particle_id(table1, i_slot,
                                                        LocalParticle_get_particle_id(part));
                    }
                }

                for (int64_t i = 0; i < n_kicks; i++) {
                    double rr = 1e-6 * LocalParticle_generate_random_double(part);
                    LocalParticle_add_to_px(part, rr);

                    // Record in table2 info about the generated kicks
                    if (record){
                        // Get a slot in table2
                        int64_t i_slot = RecordIndex_get_slot(table2_index);
                        // The returned slot id is negative if record is NULL or if record is full
                        // printf("i_slot %d\n", (int)i_slot);

                        if (i_slot>=0){
                                Table2Data_set_generated_rr(table2, i_slot, rr);
                                Table2Data_set_at_element(table2, i_slot,
                                                            LocalParticle_get_at_element(part));
                                Table2Data_set_at_turn(table2, i_slot,
                                                            LocalParticle_get_at_turn(part));
                                Table2Data_set_particle_id(table2, i_slot,
                                                            LocalParticle_get_particle_id(part));
                        }
                    }
                }

            //end_per_particle_block
        }
        ''')

        # Checks

    for context in xo.context.get_test_contexts():
        print(f"Test {context.__class__}")

        n_kicks0 = 5
        n_kicks1 = 3
        tracker = xt.Tracker(_context=context, line=xt.Line(elements = [
            TestElement(n_kicks=n_kicks0), TestElement(n_kicks=n_kicks1)]))
        tracker.line._needs_rng = True

        record = tracker.start_internal_logging_for_elements_of_type(TestElement,
                                    capacity={'table1': 10000, 'table2': 10000})

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        tracker.track(part, num_turns=num_turns0)
        tracker.track(part, num_turns=num_turns1)

        part._move_to(_context=xo.ContextCpu())
        record._move_to(_context=xo.ContextCpu())

        num_turns = num_turns0 + num_turns1
        num_particles = len(part.x)

        table1 = record.table1
        table2 = record.table2
        num_recorded_tab1 = table1._index.num_recorded
        num_recorded_tab2 = table2._index.num_recorded

        assert num_recorded_tab1 == 2 * (num_particles * num_turns)
        assert num_recorded_tab2 == (num_particles * num_turns * (n_kicks0 + n_kicks1))

        assert np.sum((table1.at_element[:num_recorded_tab1] == 0)) == (num_particles * num_turns)
        assert np.sum((table1.at_element[:num_recorded_tab1] == 1)) == (num_particles * num_turns)
        assert np.sum((table2.at_element[:num_recorded_tab2] == 0)) == (num_particles * num_turns
                                                * n_kicks0)
        assert np.sum((table2.at_element[:num_recorded_tab2] == 1)) == (num_particles * num_turns
                                                * n_kicks1)
        for i_turn in range(num_turns):
            assert np.sum((table1.at_turn[:num_recorded_tab1] == i_turn)) == 2 * num_particles
            assert np.sum((table2.at_turn[:num_recorded_tab2] == i_turn)) == (num_particles
                                                                * (n_kicks0 + n_kicks1))
        # Check reached capacity
        record = tracker.start_internal_logging_for_elements_of_type(
                                                            TestElement,
                                            capacity={'table1': 20, 'table2': 15})

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        tracker.track(part, num_turns=num_turns0)
        tracker.track(part, num_turns=num_turns1)

        table1 = record.table1
        table2 = record.table2
        num_recorded_tab1 = table1._index.num_recorded
        num_recorded_tab2 = table2._index.num_recorded

        assert num_recorded_tab1 == 20
        assert num_recorded_tab2 == 15


        # Check stop
        record = tracker.start_internal_logging_for_elements_of_type(
                                            TestElement,
                                            capacity={'table1': 1000, 'table2': 1000})

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        num_particles = len(part.x)

        tracker.track(part, num_turns=num_turns0)
        tracker.stop_internal_logging_for_elements_of_type(TestElement)
        tracker.track(part, num_turns=num_turns1)

        part._move_to(_context=xo.ContextCpu())
        record._move_to(_context=xo.ContextCpu())

        num_turns = num_turns0

        table1 = record.table1
        table2 = record.table2
        num_recorded_tab1 = table1._index.num_recorded
        num_recorded_tab2 = table2._index.num_recorded

        assert num_recorded_tab1 == 2 * (num_particles * num_turns)
        assert num_recorded_tab2 == (num_particles * num_turns * (n_kicks0 + n_kicks1))

        assert np.sum((table1.at_element[:num_recorded_tab1] == 0)) == (num_particles * num_turns)
        assert np.sum((table1.at_element[:num_recorded_tab1] == 1)) == (num_particles * num_turns)
        assert np.sum((table2.at_element[:num_recorded_tab2] == 0)) == (num_particles * num_turns
                                                * n_kicks0)
        assert np.sum((table2.at_element[:num_recorded_tab2] == 1)) == (num_particles * num_turns
                                                * n_kicks1)
        for i_turn in range(num_turns):
            assert np.sum((table1.at_turn[:num_recorded_tab1] == i_turn)) == 2 * num_particles
            assert np.sum((table2.at_turn[:num_recorded_tab2] == i_turn)) == (num_particles
                                                                * (n_kicks0 + n_kicks1))

        # Collective
        n_kicks0 = 5
        n_kicks1 = 3
        elements = [
            TestElement(n_kicks=n_kicks0, _context=context), TestElement(n_kicks=n_kicks1)]
        elements[0].iscollective = True
        tracker = xt.Tracker(_context=context, line=xt.Line(elements=elements))
        tracker.line._needs_rng = True

        record = tracker.start_internal_logging_for_elements_of_type(
                                            TestElement,
                                            capacity={'table1': 1000, 'table2': 1000})

        part = xp.Particles(_context=context, p0c=6.5e12, x=[1e-3,2e-3,3e-3])
        num_turns0 = 10
        num_turns1 = 3
        tracker.track(part, num_turns=num_turns0)
        tracker.stop_internal_logging_for_elements_of_type(TestElement)
        tracker.track(part, num_turns=num_turns1)

        # Checks
        part._move_to(_context=xo.ContextCpu())
        record._move_to(_context=xo.ContextCpu())
        num_turns = num_turns0
        num_particles = len(part.x)

        table1 = record.table1
        table2 = record.table2
        num_recorded_tab1 = table1._index.num_recorded
        num_recorded_tab2 = table2._index.num_recorded

        assert num_recorded_tab1 == 2 * (num_particles * num_turns)
        assert num_recorded_tab2 == (num_particles * num_turns * (n_kicks0 + n_kicks1))

        assert np.sum((table1.at_element[:num_recorded_tab1] == 0)) == (num_particles * num_turns)
        assert np.sum((table1.at_element[:num_recorded_tab1] == 1)) == (num_particles * num_turns)
        assert np.sum((table2.at_element[:num_recorded_tab2] == 0)) == (num_particles * num_turns
                                                * n_kicks0)
        assert np.sum((table2.at_element[:num_recorded_tab2] == 1)) == (num_particles * num_turns
                                                * n_kicks1)
        for i_turn in range(num_turns):
            assert np.sum((table1.at_turn[:num_recorded_tab1] == i_turn)) == 2 * num_particles
            assert np.sum((table2.at_turn[:num_recorded_tab2] == i_turn)) == (num_particles
                                                                * (n_kicks0 + n_kicks1))