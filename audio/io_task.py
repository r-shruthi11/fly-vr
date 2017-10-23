# -*- coding: utf-8 -*-
import sys
import threading
import time

import PyDAQmx as daq
from PyDAQmx.DAQmxCallBack import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *

from itertools import chain, islice

import math

import numpy as np

import common.tools

from common.concurrent_task import ConcurrentTask
from audio.stimuli import AudioStim, SinStim, AudioStimPlaylist
from common.plot_task import plot_task_main
from common.log_task import log_audio_task_main

class IOTask(daq.Task):
    """
    IOTask encapsulates the an input-output task that communicates with the NIDAQ. It works with a list of input or
    output channel names.
    """
    def __init__(self, dev_name="Dev1", cha_name=["ai0"], cha_type="input", limits=10.0, rate=10000.0,
                 num_samples_per_chan=10000, num_samples_per_event=None, digital=False, has_callback=True,
                 fictrac_frame_num=None):
        # check inputs
        daq.Task.__init__(self)

        if not isinstance(cha_name, list):
            cha_name = [cha_name]


        self.fictrac_frame_num = fictrac_frame_num

        self.digital = digital

        self.read = daq.int32()
        self.read_float64 = daq.float64()

        self.limits=limits
        self.cha_type = cha_type
        self.cha_name = [dev_name + '/' + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_name)
        self.num_channels = len(cha_name)
        self.num_samples_per_chan = num_samples_per_chan
        self.num_samples_per_event = num_samples_per_event  # self.num_samples_per_chan*self.num_channels

        if self.num_samples_per_event is None:
            self.num_samples_per_event = num_samples_per_chan

        clock_source = None  # use internal clock
        self.callback = None
        self.data_gen = None  # called at start of callback
        self.data_rec = None  # called at end of callback

        if self.cha_type is "input":
            if not self.digital:
                self.CreateAIVoltageChan(self.cha_string, "", DAQmx_Val_RSE, -limits, limits, DAQmx_Val_Volts, None)
            else:
                self.CreateDIChan(self.cha_string, "", daq.DAQmx_Val_ChanPerLine)

            if has_callback:
                self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer, self.num_samples_per_event, 0)
                self.CfgInputBuffer(self.num_samples_per_chan * self.num_channels * 4)

        elif self.cha_type is "output":
            if not self.digital:
                self.CreateAOVoltageChan(self.cha_string, "", -limits, limits, DAQmx_Val_Volts, None)
            else:
                self.CreateDOChan(self.cha_string, "", daq.DAQmx_Val_ChanPerLine)

        if not digital:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.float64)  # init empty data array
        else:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.uint8)

        self.CfgSampClkTiming(clock_source, rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.num_samples_per_chan)
        self.AutoRegisterDoneEvent(0)

        if has_callback:
            self._data_lock = threading.Lock()
            self._newdata_event = threading.Event()
            if self.cha_type is "output":

                self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Transferred_From_Buffer, self.num_samples_per_event, 0)
                # ensures continuous output and avoids collision of old and new data in buffer
                self.SetAODataXferReqCond(self.cha_name[0], DAQmx_Val_OnBrdMemEmpty)
                self.SetWriteRegenMode(DAQmx_Val_DoNotAllowRegen)
                self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)

                self.EveryNCallback()  # fill buffer on init
        else:
            self.SetWriteRegenMode(DAQmx_Val_AllowRegen)
            self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)

        # if self.cha_type == "output":
        #     tranCond = daq.int32()
        #     self.GetAODataXferReqCond(self.cha_name[0], daq.byref(tranCond))
        #     print("Channel Type:" + self.cha_type + ", Transfer Cond: " + str(tranCond))

    def stop(self):
        if self.data_gen is not None:
            self._data = self.data_gen.close()  # close data generator
        if self.data_rec is not None:
            for data_rec in self.data_rec:
                data_rec.finish()
                data_rec.close()

    def set_data_generator(self, data_generator):
        """
        Set the data generator for the audio stimulus directly.

        :param data_generator: A generator function of audio data.
        """
        with self._data_lock:
            chunked_gen = chunker(data_generator, chunk_size=self.num_samples_per_chan)
            self.data_gen = chunked_gen

    def send(self, data):
        if self.cha_type == "input":
            raise ValueError("Cannot send on an input channel, it must be an output channel.")
        if self.digital:
            self.WriteDigitalLines(data.shape[0], False, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, data, None, None)
        else:
            self.WriteAnalogF64(data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, data, daq.byref(self.read), None)

    # FIX: different functions for AI and AO task types instead of in-function switching?
    #      or maybe pass function handle?
    def EveryNCallback(self):
        with self._data_lock:
            systemtime = time.clock()
            if self.data_gen is not None:
                self._data = self.data_gen.next()  # get data from data generator

            if self.cha_type is "input":
                if not self.digital:
                    self.ReadAnalogF64(DAQmx_Val_Auto, 1.0, DAQmx_Val_GroupByScanNumber,
                                   self._data, self.num_samples_per_chan * self.num_channels, daq.byref(self.read), None)
                else:
                    numBytesPerSamp = daq.int32()
                    self.ReadDigitalLines(self.num_samples_per_chan, 1.0, DAQmx_Val_GroupByScanNumber,
                                          self._data, self.num_samples_per_chan * self.num_channels,
                                          byref(self.read),  byref(numBytesPerSamp), None)

            elif self.cha_type is "output":
                if not self.digital:
                    self.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel,
                                    self._data, daq.byref(self.read), None)
                else:
                    self.WriteDigitalLines(self._data.shape[0], False, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel, self._data, None, None)

            # Send the data to a callback if requested.
            if self.data_rec is not None:
                for data_rec in self.data_rec:
                    if self._data is not None:
                        data_rec.send((self._data, systemtime))

            self._newdata_event.set()
        return 0  # The function should return an integer

    def DoneCallback(self, status):
        print("Done status", status)
        return 0  # The function should return an integer

@common.tools.coroutine
def data_generator_test(channels=1, num_samples=10000, dtype=np.float64):
    '''generator yields next chunk of data for output'''
    # generate all stimuli

    max_value = 5

    if dtype == np.uint8:
        max_value = 1

    data = list()
    for ii in range(2):
        # t = np.arange(0, 1, 1.0 / max(100.0 ** ii, 100))
        # tmp = np.tile(0.2 * np.sin(5000 * t).astype(np.float64), (channels, 1)).T

        # simple ON/OFF pattern
        tmp = max_value * ii * np.ones((channels, num_samples)).astype(dtype).T
        data.append(np.ascontiguousarray(tmp))  # `ascont...` necessary since `.T` messes up internal array format
    count = 0  # init counter
    try:
        while True:
            count += 1
            # print("{0}: generating {1}".format(count, data[(count-1) % len(data)].shape))
            yield data[(count - 1) % len(data)]
    except GeneratorExit:
        print("   cleaning up datagen.")

def io_task_main(message_pipe, RUN, DAQ_READY, FICTRAC_FRAME_NUM):

    # If we receive a data denerator before created the tasks, lets cache it so we
    # can set it.
    cached_data_generator = None

    # Keep the daq controller task running until exit is signalled by main thread via RUN shared memory variable
    while RUN.value != 0:

        # Message loop that waits for start signal
        wait_for_start = True
        while wait_for_start and RUN.value != 0:
            if message_pipe.poll(0.1):
                try:
                    msg = message_pipe.recv()

                    # If we have received a stimulus object, feed this object to output task for playback
                    if isinstance(msg, AudioStim) | isinstance(msg, AudioStimPlaylist):
                        cached_data_generator = msg.data_generator()
                    elif isinstance(msg, list):
                        command = msg[0]
                        options = msg[1]
                        if command == "START":
                            wait_for_start = False
                except:
                    print("Bad message!")
                    pass

        # Get the input and output channels from the options
        output_chans = ["ao" + str(s) for s in options.analog_out_channels]
        input_chans = ["ai" + str(s) for s in options.analog_in_channels]

        taskAO = IOTask(cha_name=output_chans, cha_type="output",
                        num_samples_per_chan=50, num_samples_per_event=50,
                        fictrac_frame_num=FICTRAC_FRAME_NUM)
        taskAI = IOTask(cha_name=input_chans, cha_type="input",
                        num_samples_per_chan=10000, num_samples_per_event=10000)

        disp_task = ConcurrentTask(task=plot_task_main, comms="pipe",
                                   taskinitargs=[input_chans,taskAI.num_samples_per_chan,10])
        disp_task.start()
        save_task = ConcurrentTask(task=log_audio_task_main, comms="queue", taskinitargs=[options.record_file, len(input_chans)])
        save_task.start()

        taskAI.data_rec = [disp_task, save_task]

        if cached_data_generator is not None:
            taskAO.set_data_generator(cached_data_generator)

        # Connect AO start to AI start
        taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

        # Arm the AO task
        # It won't start until the start trigger signal arrives from the AI task
        taskAO.StartTask()

        # Start the AI task
        # This generates the AI start trigger signal and triggers the AO task
        taskAI.StartTask()

        # Signal that the DAQ is ready and aquiring samples
        DAQ_READY.value = 1

        while RUN.value != 0:
            if message_pipe.poll(0.1):
                try:
                    msg = message_pipe.recv()

                    # If we have received a stimulus object, feed this object to output task for playback
                    if isinstance(msg, AudioStim) | isinstance(msg, AudioStimPlaylist):
                        taskAO.set_data_generator(msg.data_generator())
                except:
                    pass

        # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
        taskAO.StopTask()
        taskAO.stop()
        taskAI.StopTask()
        taskAI.stop()

    taskAO.ClearTask()
    taskAI.ClearTask()

    DAQ_READY.value = 0


def chunker(gen, chunk_size=100):
    next_chunk = None
    curr_data_sample = 0
    curr_chunk_sample = 0
    data = None
    num_samples = 0
    while True:

        if curr_data_sample == num_samples:
            data = gen.next()
            curr_data_sample = 0
            num_samples = data.shape[0]

            # If this is our first chunk, use its dimensions to figure out the number of columns
            if next_chunk is None:
                chunk_shape = list(data.shape)
                chunk_shape[0] = chunk_size
                next_chunk = np.zeros(tuple(chunk_shape), dtype=data.dtype)

        # We want to add at most chunk_size samples to a chunk. We need to see if the current data will fit. If it does,
        # copy the whole thing. If it doesn't, just copy what will fit.
        sz = min(chunk_size-curr_chunk_sample, num_samples-curr_data_sample)
        if data.ndim == 1:
            next_chunk[curr_chunk_sample:(curr_chunk_sample + sz)] = data[curr_data_sample:(curr_data_sample + sz)]
        else:
            next_chunk[curr_chunk_sample:(curr_chunk_sample+sz), :] = data[curr_data_sample:(curr_data_sample + sz), :]

        curr_chunk_sample = curr_chunk_sample + sz
        curr_data_sample = curr_data_sample + sz

        if curr_chunk_sample == chunk_size:
            curr_chunk_sample = 0
            yield next_chunk.copy()


def test_hardware_singlepoint(rate=1000.0, chunk_size=100):
    taskHandle = TaskHandle()
    samplesPerChannelWritten = daq.int32()
    isLate = daq.c_uint32()

    stim = SinStim(frequency=250, amplitude=1, phase=0, sample_rate=rate, duration=2000, pre_silence=300, post_silence=300)
    chunk_gen = chunker(stim.data_generator(), 100)

    try:
        DAQmxCreateTask("", byref(taskHandle))
        DAQmxCreateAOVoltageChan(taskHandle, "/Dev1/ao0", "", -10.0, 10.0, DAQmx_Val_Volts, None)
        DAQmxCfgSampClkTiming(taskHandle, "", rate, DAQmx_Val_Rising, DAQmx_Val_HWTimedSinglePoint, stim.data.shape[0])

        DAQmxStartTask(taskHandle)

        for i in xrange(stim.data.shape[0]/chunk_size):
            DAQmxWriteAnalogF64(taskHandle, chunk_size, 1, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByChannel,
                                chunk_gen.next(), daq.byref(samplesPerChannelWritten), None)
            DAQmxWaitForNextSampleClock(taskHandle, 10, daq.byref(isLate))
            assert isLate.value == 0, "%d" % isLate.value

    except DAQError as err:
        print "DAQmx Error: %s" % err
    finally:
        if taskHandle:
            # DAQmx Stop Code
            DAQmxStopTask(taskHandle)
            DAQmxClearTask(taskHandle)

def main():
   pass

if __name__ == "__main__":
    main()
