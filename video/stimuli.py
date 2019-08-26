import numpy as np
import scipy
from scipy import io
from scipy import signal
import h5py
import abc

class VideoStim(object, metaclass=abc.ABCMeta):
    """
    The VideoStim class is base class meant to encapsulate common functionality and implementation details found in
    any audio stimulus. Mainly, this includes the generation and storage of audio signal data, basic information about
    the stimulus, inclusion of pre and post silence signals to the main signal, etc. If you wish to add new audio
    stimulus functionality you should create a new class that inherits from this class and implements its abstract
    methods.
    """

    def __init__(self, sample_rate, duration, window=None, intensity=1.0, pre_silence = 0, post_silence = 0, attenuator=None,
                 frequency=None, max_value=10.0, min_value=-10.0, next_event_callbacks=None):
        """
        Create an audio stimulus object that encapsulates the generation of the underlying audio
        data.
        :param int sample_rate: The sample rate in Hz of the underlying audio data.
        :param int duration: The duration of the sound in milliseconds
        :param int pre_silence: The duration (in milliseconds) of silence to add to the start of the signal.
        :param int post_silence: The duration (in milliseconds) of silence to add to the end of the signal.
        :param list next_event_callbacks: A list of control functions to call whenever the generator produced by this
        class yields a value.
        """

        # Attach event next callbacks to this object, since it is a signal producer
        super(VideoStim, self).__init__(next_event_callbacks)

        self.__sample_rate = sample_rate
        self.__duration = duration
        self.__pre_silence = pre_silence
        self.__post_silence = post_silence
        self.__attenuator = attenuator
        self.__frequency = frequency
        self.__intensity = intensity
        self.__max_value = max_value
        self.__min_value = min_value

        self.__window = window

        # How many samples have been generated by calls to data_generator() iterators
        self.num_samples_generated = 0

        # Setup a dictionary for the parameters of the stimulus. We will send this as part
        # of an event message to the next_event_callbacks
        self.event_message = {"name": type(self).__name__,
                              "sample_rate": sample_rate, "duration": duration, "pre_silence": pre_silence,
                              "post_silence": post_silence, "frequency": frequency, "intensity": intensity,
                              "max_clamp_value": max_value, "min_clamp_value": min_value}
        if attenuator is None:
            self.event_message["attenuation"] = None
        else:
            self.event_message["attenuation"] = np.column_stack((attenuator.frequencies, attenuator.factors))

        # Initialize data to null
        self.__data = []

    def _gen_silence(self, silence_duration):
        """
        Little helper function to generate silence data.

        :param int silence_duration: Amount of silence to generate in milliseconds.
        :return: The silence signal.
        :rtype: numpy.ndarray
        """
        return np.zeros(int(np.ceil((silence_duration/1000.0) * self.sample_rate)))

    def _add_silence(self, data):
        """
        A helper function to add pre and post silence to a generated signal.

        :param numpy.ndarray data: The data to add silence to.
        :return: The data with silence added to its start and end.
        :rtype: numpy.ndarray
        """
        return np.concatenate([self._gen_silence(self.pre_silence), data, self._gen_silence(self.post_silence)])

    @abc.abstractmethod
    def _generate_data(self):
        """
        Generate any internal data necessary for the stimulus, called when parameters
        are changed only. This is so we don't have to keep generating the data with every
        call to get_data. This method should be overloaded in any sub-class to generate the
        actual audio data.

        :return: The data representing the stimulus.
        :rtype: numpy.ndarray
        """

    @property
    def data(self):
        """
        Get the voltage signal data associated with this stimulus.

        :return: A 1D numpy.ndarray of data that can be passed directly to the DAQ.
        :rtype: numpy.ndarray
        """
        return self.__data

    @data.setter
    def data(self, data):
        """
        Set the data for the audio stimulus directly. This function will add any required silence
        as a side-effect. Sub-classes of VideoStim should use this setter.

        :param numpy.ndarray data: The raw audio signal data representing this stimulus.
        """

        # If the user provided an attenuator, attenuate the signal
        if self.__attenuator is not None:
            data = self.__attenuator.attenuate(data, self.__frequency)

        data = self._add_silence(data)

        # Multiply the signal by the intensity factor
        data = data * self.__intensity

        self.__data = data

        # Perform limit check on data, make sure we are not exceeding
        if data.max() > self.__max_value:
            raise ValueError("Audio stimulus value exceeded max level!")

        if data.min() < self.__min_value:
            raise ValueError("Audio stimulus value lower than min level!")

    def data_generator(self):
        """
        Return a generator that yields the data member when next is called on it. Simply provides another interface to
        the same data stored in the data member.

        :return: A generator that yields an array containing the sample data.
        """
        while True:
            self.num_samples_generated = self.num_samples_generated + self.data.shape[0]
            self.trigger_next_callback(message_data=self.event_message, num_samples=self.data.shape[0])

            yield SampleChunk(data=self.data, producer_id=self.producer_id)

    @property
    def sample_rate(self):
        """
        Get the sample rate of the audio stimulus in Hz.

        :return: The sample rate of the audio stimulus in Hz.
        :rtype: int
        """
        return self.__sample_rate

    @sample_rate.setter
    def sample_rate(self, sample_rate):
        """
        Set the sample rate of the audio stimulus in Hz.

        :param int sample_rate: The sample rate of the audio stimulus in Hz.
        """
        self.__sample_rate = sample_rate
        self.data = self._generate_data()

    @property
    def duration(self):
        """
        Get the duration of the audio signal in milliseconds.

        :return: The duration of the audio signal in milliseconds.
        :rtype: int
        """
        return self.__duration

    @duration.setter
    def duration(self, duration):
        """
        Set the duration of the audio signal in milliseconds.

        :param int duration: The duration of the audio signal in milliseconds.
        """
        self.__duration = duration
        self.data = self._generate_data()

    @property
    def intensity(self):
        """
        Get the intensity of the audio signal. This is a scalar multiplicative factor of the signal.

        :return: A scalar multiplicative factor of the signal.
        :rtype: double
        """
        return self.__intensity

    @intensity.setter
    def intensity(self, intensity):
        """
         Set the intensity of the audio signal. This is a scalar multiplicative factor of the signal.

        :param double intensity: A scalar multiplicative factor of the signal.
        """
        self.__intensity = intensity
        self.data = self._generate_data()

    @property
    def pre_silence(self):
        """
        Get the amount (in milliseconds) of pre-silence added to the audio signal.

        :return: Get the amount (in milliseconds) of pre-silence added to the audio signal.
        :rtype: int
        """
        return self.__pre_silence

    @pre_silence.setter
    def pre_silence(self, pre_silence):
        """
        Set the amount (in milliseconds) of pre-silence added to the audio signal.

        :param int pre_silence: The amount (in milliseconds) of pre-silence added to the audio signal.
        """
        self.__pre_silence = pre_silence
        self.data = self._generate_data()

    @property
    def post_silence(self):
        """
        Set the amount (in milliseconds) of post-silence added to the audio signal.

        :return: The amount (in milliseconds) of post-silence added to the audio signal.
        """
        return self.__post_silence

    @post_silence.setter
    def post_silence(self, post_silence):
        """
        Set the amount (in milliseconds) of post-silence added to the audio signal.

        :param int post_silence: The amount (in milliseconds) of post-silence added to the audio signal.
        """
        self.__post_silence = post_silence
        self.data = self._generate_data()

    @property
    def attenuator(self):
        """
        Get the attenuator object used to attenuate the sin signal.

        :return: The attenuator object used to attenuate the sin signal.
        :rtype: audio.attenuation.Attenuator
        """
        return self.__attenuator

    @attenuator.setter
    def attenuator(self, attenuator):
        """
        Set the attenuator object used to attenuate the sin signal.

        :param audio.stimuli.Attenuator attenuator: The attenuator object used to attenuate the sin signal.
        """
        self.__attenuator = attenuator
        self.data = self._generate_data()

    @property
    def frequency(self):
        """
        Get the frequency of the sin signal in Hz.

        :return: The frequency of the sin signal in Hz.
        :rtype: float
        """
        return self.__frequency

    @frequency.setter
    def frequency(self, frequency):
        """
        Set the frequency of the sin signal in Hz.

        :param float frequency: The frequency of the sin signal in Hz.
        """
        self.__frequency = frequency
        self.data = self._generate_data()

class LoomingDot(VideoStim):
    """
       The LoomingDot class provides a simple interface for generating sinusoidal audio stimulus data
       appropriate for feeding directly as voltage signals to a DAQ for playback. It allows parameterization
       of the sinusoid as well as attenuation by a custom attenuation object.
    """

    def __init__(self, window, intensity=1.0, pre_silence=0,
                 post_silence=0, attenuator=None, next_event_callbacks=None):

        # Initiatialize the base class members
        super(LoomingDot, self).__init__(window=window, sample_rate=sample_rate, duration=duration, intensity=intensity,
                                      pre_silence=pre_silence, post_silence=post_silence, attenuator=attenuator,
                                      frequency=frequency, next_event_callbacks=next_event_callbacks)

        self.screen = visual.GratingStim(win=mywin, size=5, pos=[0,0], sf=50, color=-1)

        # self.__amplitude = amplitude
        # self.__phase = phase

        # Add class specific parameters to the event message that is sent to functions in next_event_callbacks from the
        # base class generator.
        self.event_message["amplitude"] = amplitude
        self.event_message["phase"] = phase

        self.data = self._generate_data()

    def data_generator(self):
        """
        Return a generator that yields the data member when next is called on it. Simply provides another interface to
        the same data stored in the data member.

        :return: A generator that yields an array containing the sample data.
        """
        print('generator?')
        while True:
            self.screen.draw()
            self.mywin.update()

            self.num_samples_generated = self.num_samples_generated + self.data.shape[0]
            self.trigger_next_callback(message_data=self.event_message, num_samples=self.data.shape[0])

            yield SampleChunk(data=self.data, producer_id=self.producer_id)

    @property
    def amplitude(self):
        """
        Get the amplitude of the sin signal.

        :return: The amplitude of the sin signal.
        :rtype: float
        """
        return self.__amplitude

    @amplitude.setter
    def amplitude(self, amplitude):
        """
        Set the amplitude of the sin signal.

        :param float amplitude: Set the amplitude of the sin signal.
        """
        self.__amplitude = amplitude
        self.data = self._generate_data()

    @property
    def phase(self):
        """
        Get the phase of the sin, in radians.

        :return: The phase of the sin, in radians.
        :rtype: float
        """
        return self.__phase

    @phase.setter
    def phase(self, phase):
        """
        Set the phase of the sin, in radians.

        :param float phase: The phase of the sin, in radians.
        """
        self.__phase = phase
        self.data = self._generate_data()

    def _generate_data(self):
        """
        Generate the sin sample data according to the parameters. Also attenuatte the signal if an attenuator
        is provided.

        :return: The sin signal data, ready to be passed to the DAQ as voltage signals.
        :rtype: numpy.ndarray
        """
        T = np.linspace(0.0, float(self.duration) / 1000.0, (float(self.sample_rate) / 1000.0) * self.duration)

        # Generate the samples of the sin wave with specified amplitude, frequency, and phase.
        data = self.amplitude * np.sin(2 * np.pi * self.frequency * T + self.phase)

        return data