import sys
import time

from flyvr.common.build_arg_parser import parse_arguments

from flyvr.video.video_server import run_video_server
from flyvr.audio.sound_server import run_sound_server
from flyvr.audio.io_task import run_io
from flyvr.common import SharedState
from flyvr.control.experiment import Experiment
from flyvr.common.concurrent_task import ConcurrentTaskThreaded as ConcurrentTask
from flyvr.common.logger import DatasetLogger, DatasetLogServer
from flyvr.fictrac.fictrac_driver import FicTracDriver, fictrac_poll_run_main
from flyvr.fictrac.replay import FicTracDriverReplay


def _get_fictrac_driver(options):
    drv = None

    if options.fictrac_config is not None:
        experiment = None
        if options.experiment:
            assert isinstance(options.experiment, Experiment)
            experiment = options.experiment

        if options.fictrac_config.endswith('.h5'):
            drv = FicTracDriverReplay(options.fictrac_config)
        else:
            drv = FicTracDriver(options.fictrac_config, options.fictrac_console_out,
                                experiment=experiment,
                                pgr_enable=options.pgr_cam_enable)

    return drv


def main_fictrac():
    options, parser = parse_arguments(return_parser=True)

    log_server = DatasetLogServer()
    logger = log_server.start_logging_server(options.record_file)

    state = SharedState(options=options, logger=logger)

    trac_drv = _get_fictrac_driver(options)
    if trac_drv is None:
        raise parser.error('Fictrac configuration not specified')

    trac_drv.run(None, state)



def main_launcher():

    try:
        options = parse_arguments()
    except ValueError as ex:
        sys.stderr.write("Invalid Config Error: \n" + str(ex) + "\n")
        sys.exit(-1)

    log_server = DatasetLogServer()
    logger = log_server.start_logging_server(options.record_file)

    state = SharedState(options=options, logger=logger)

    trac_drv = _get_fictrac_driver(options)

    if trac_drv is not None:
        fictrac_task = ConcurrentTask(task=trac_drv.run, comms="pipe",
                                      taskinitargs=[None, state])
        fictrac_task.start()

        # Wait till FicTrac is processing frames
        while state.FICTRAC_READY == 0 and state.is_running_well():
            time.sleep(0.2)

    # start the other mainloops
    daq = ConcurrentTask(task=run_io, comms=None, taskinitargs=[options])
    daq.start()
    video = ConcurrentTask(task=run_video_server, comms=None, taskinitargs=[options])
    video.start()
    audio = ConcurrentTask(task=run_sound_server, comms=None, taskinitargs=[options])
    audio.start()

    if state.is_running_well():

        print("Delaying start by " + str(options.start_delay) + " ...")
        time.sleep(options.start_delay)

        # Send a signal to the DAQ to start playback and acquisition
        print("Signalling DAQ Start")
        state.START_DAQ = 1

        # Wait until we get a ready message from the DAQ task
        while state.DAQ_READY == 0 and state.is_running_well():
            time.sleep(0.2)

        # Wait till the user presses enter to end session
        if state.is_running_well():
            input("Press ENTER to end session ... ")

