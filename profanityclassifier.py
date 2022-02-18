from __future__ import division
import os 
import re
import sys
import datetime 
import time 
import pyaudio
import multiprocessing as mp
from profanity import profanity 
from google.cloud import speech
from six.moves import queue


os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'C:/Users/Benjamin/Downloads/Speech Problems-97a9a08825c0.json'

# Audio recording parameters
RATE = 44100
CHUNK = int(RATE / 30)  # 100ms


class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    
    '''
    ***************
    so we need to figure out why this is looping and continues to update responses printing them -- we want to censor out all potential
    candidates and then intelligently reduce that number to an acceptable margin of error / risk so we need everything returned but not printed
    
    may need to make our own custom profanity dataset because this one in the profanity library is severly limited 
    or we could do it by profanity level like G,PG,PG-13,R, etc... and have that selectable
    ***************
    '''
    
    now = []
    tripwire = False 
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = " " * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            profane = profanity.contains_profanity(transcript+overwrite_chars)
            print((transcript + overwrite_chars))
            print(profane)
            
            if profane == True: 
                tripwire = True 
                now.append(datetime.datetime.now())
                print(now[-1])

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Exiting..")
                break

            num_chars_printed = 0

def callandresponse():
    paud = pyaudio.PyAudio()
    
    x = True 
    start = datetime.datetime.now()
    CHANNELS = 1
    RATE = 44100
    
    streamIn = paud.open(
        format= pyaudio.paFloat32,
        channels= CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=10000
    )
    
    streamOut = paud.open(
        format= pyaudio.paFloat32,
        channels= CHANNELS,
        rate= RATE,
        output=True,
        frames_per_buffer=10000
    )
    
    while streamIn.is_active():
        audioData = streamIn.read(20000)
        delta = datetime.datetime.now() - start
        if delta.seconds > 1000:
            x = False
        if x == True:
            streamOut.write(audioData)


def main():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = "en-US"  # a BCP-47 language tag

    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        try: 
            listen_print_loop(responses)
        except:
            main()
            return False



if __name__ == "__main__":
    p = mp.Process(target = main)
    q = mp.Process(target = callandresponse)
    
    p.start()
    q.start()