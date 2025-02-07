import pytest

from flyvr.audio.sound_server import SoundServer
from flyvr.audio.stimuli import SinStim
from flyvr.audio.signal_producer import SampleChunk
from flyvr.common import SharedState
from flyvr.common.dottable import Dottable
from flyvr.common.logger import DatasetLogServer


@pytest.mark.use_soundcard
def test_list_devices():
    from io import StringIO
    s = StringIO()
    SoundServer.list_supported_asio_output_devices(out=s)
    assert 'ASIO' in s.getvalue()


@pytest.mark.use_soundcard
def test_play_sin(tmpdir):
    import time
    import h5py

    stim1 = SinStim(frequency=200, amplitude=1.0, phase=0.0, sample_rate=44100, duration=10000)

    dest = tmpdir.join('test.h5').strpath

    with DatasetLogServer() as log_server:
        logger = log_server.start_logging_server(dest)

        options = Dottable(wait=False)
        shared_state = SharedState(options, logger)

        sound_server = SoundServer(flyvr_shared_state=shared_state)
        sound_server.start_stream(frames_per_buffer=SoundServer.DEFAULT_CHUNK_SIZE)
        sound_server.queue.put(stim1)
        time.sleep(1.5)

        sound_server.quit()

    with h5py.File(dest, mode='r') as h5:
        assert h5['audio']['chunk_synchronization_info'].shape[-1] == SampleChunk.SYNCHRONIZATION_INFO_NUM_FIELDS
