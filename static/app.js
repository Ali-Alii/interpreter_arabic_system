const $ = id => document.getElementById(id);
let recording = false, busy = false, starting = false, settingUp = false, stream, context, source, recorder, mute;
let samples = [], sampleCount = 0, startedAt = 0, clock, animation, analyser, playbackUrl, resultText = '';
let pendingAudio = null, engineReady = false;
let lastSetupStage;
const retry = document.createElement('button');
retry.id = 'transcribe-recording'; retry.className = 'text-button'; retry.hidden = true;
retry.textContent = 'Transcribe this recording';
$('playback').append(retry);
retry.addEventListener('click', () => { if (pendingAudio) transcribe(pendingAudio); });
const saveAudio = document.createElement('a');
saveAudio.className = 'text-button'; saveAudio.textContent = 'Save recording ↓';
saveAudio.download = 'sawt-recording.wav'; $('playback').append(saveAudio);
const canvas = $('wave'), pen = canvas.getContext('2d');
function message(text, error = false) { $('message').textContent = text; $('message').className = error ? 'error' : ''; }
function controls() {
  $('mic').disabled = busy || starting;
  $('upload').disabled = busy || starting || recording;
  $('upload-label').classList.toggle('disabled', $('upload').disabled);
  $('prepare').disabled = busy || starting || recording || settingUp;
  retry.disabled = busy || starting || recording || !engineReady;
}
function draw() {
  pen.clearRect(0, 0, canvas.width, canvas.height);
  const bins = new Uint8Array(64);
  if (analyser) analyser.getByteFrequencyData(bins);
  pen.fillStyle = recording ? '#2a6954' : '#c7d2bf';
  for (let i = 0; i < 52; i++) {
    const h = recording ? Math.max(3, bins[i] / 255 * 58) : 3;
    pen.fillRect(i * 10 + 2, (70 - h) / 2, 3, h);
  }
  if (recording) animation = requestAnimationFrame(draw);
}
async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be processed.');
  return data;
}
async function status() {
  try {
    const s = await api('/api/status');
    engineReady = s.state === 'ready';
    $('engine-status').textContent = {ready:`Engine ready · ${s.device === 'cuda' ? 'GPU' : 'CPU'}`, loading:'Loading speech model…', not_loaded:'Model ready to load', error:'Engine needs attention'}[s.state];
    $('engine-status').className = `status ${s.state}`;
    const wasSettingUp = settingUp;
    settingUp = !!s.setup && ['downloading','installing','loading'].includes(s.setup.stage) && s.state !== 'ready';
    if (settingUp) {
      $('engine-status').textContent = s.setup.model_download_percent != null ? `Setting up · weights ${s.setup.model_download_percent}%` : 'Setting up speech engine…';
      if (s.setup.gpu_download_percent != null) $('engine-status').textContent = `Model ${s.setup.model_download_percent ?? 0}% · GPU download ${s.setup.gpu_download_percent}%`;
      if (lastSetupStage !== s.setup.stage && !recording && !starting && !busy && !pendingAudio) message('You can record and listen back now. Transcription will be available when the speech model finishes downloading.');
    } else if (s.setup?.stage === 'error' && lastSetupStage !== 'error' && !busy && !recording && !pendingAudio) {
      message(s.setup.message, true);
    } else if (wasSettingUp && s.state === 'ready') {
      message(pendingAudio ? 'The speech model is ready. Click “Transcribe this recording” below the audio player.' : 'The speech model is ready. Tap the microphone to start.');
    }
    lastSetupStage = s.setup?.stage;
    controls();
  } catch { engineReady = false; $('engine-status').textContent = 'Server disconnected'; controls(); }
}
function wav(chunks, count, rate) {
  const bytes = new ArrayBuffer(44 + count * 2), view = new DataView(bytes);
  const str = (at, s) => { for (let i = 0; i < s.length; i++) view.setUint8(at + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  str(36, 'data'); view.setUint32(40, count * 2, true);
  let pos = 44;
  for (const chunk of chunks) for (const sample of chunk) {
    const s = Math.max(-1, Math.min(1, sample)); view.setInt16(pos, s < 0 ? s * 32768 : s * 32767, true); pos += 2;
  }
  return new Blob([bytes], {type:'audio/wav'});
}
async function release() {
  clearInterval(clock); cancelAnimationFrame(animation);
  stream?.getTracks().forEach(t => t.stop());
  recorder?.disconnect(); source?.disconnect(); mute?.disconnect();
  if (context && context.state !== 'closed') await context.close();
  analyser = null; stream = null; recorder = null; source = null; mute = null;
}
async function start() {
  starting = true; controls();
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access requires localhost or HTTPS. Open http://127.0.0.1:8000.');
    stream = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1, echoCancellation:false, noiseSuppression:false, autoGainControl:false}});
    context = new AudioContext(); await context.resume();
    await context.audioWorklet.addModule('/static/recorder-worklet.js');
    source = context.createMediaStreamSource(stream);
    recorder = new AudioWorkletNode(context, 'pcm-recorder');
    mute = context.createGain(); mute.gain.value = 0;
    analyser = context.createAnalyser(); analyser.fftSize = 128;
    samples = []; sampleCount = 0;
    recorder.port.onmessage = event => {
      if (!recording) return;
      const remaining = Math.floor(context.sampleRate * 120) - sampleCount;
      const chunk = event.data.subarray(0, Math.max(0, remaining));
      if (chunk.length) { samples.push(chunk); sampleCount += chunk.length; }
      if (remaining <= event.data.length) stop();
    };
    source.connect(recorder); recorder.connect(mute); mute.connect(context.destination); source.connect(analyser);
    recording = true; startedAt = performance.now();
    $('mic').classList.add('recording'); $('mic').setAttribute('aria-label', 'Stop recording and transcribe');
    $('record-label').textContent = 'Listening… tap to finish';
    message('Speak naturally and pronounce each ending. No fixed pauses are needed. Up to two minutes.');
    clock = setInterval(() => {
      const s = Math.min(120, Math.floor((performance.now() - startedAt) / 1000));
      $('timer').innerHTML = `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')} <span>/ 02:00</span>`;
      if (s >= 120) stop();
    }, 200);
    draw();
  } catch (error) {
    recording = false; await release();
    message(error.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow it in your browser and try again.' : error.message, true);
  } finally { starting = false; controls(); }
}
async function stop() {
  if (!recording) return;
  recording = false; busy = true; controls();
  const blob = wav(samples, sampleCount, context.sampleRate);
  await release(); samples = []; draw();
  $('mic').classList.remove('recording'); $('mic').setAttribute('aria-label', 'Start recording');
  await acceptRecording(blob);
}
async function acceptRecording(blob) {
  pendingAudio = blob;
  if (playbackUrl) URL.revokeObjectURL(playbackUrl);
  playbackUrl = URL.createObjectURL(blob); $('audio').src = playbackUrl; saveAudio.href = playbackUrl;
  $('playback').hidden = false; retry.hidden = false;
  resultText = ''; $('transcript').hidden = true; $('empty').hidden = false;
  $('copy').disabled = true; $('details').hidden = true; $('result-meta').hidden = true;
  busy = false; $('record-label').textContent = 'Tap to record again'; controls();
  if (engineReady) return transcribe(blob);
  $('result-state').textContent = 'Recording ready · model not ready';
  message('Your recording is ready to play below. Keep this page open or save the WAV. When the model is ready, click “Transcribe this recording”.');
}
async function transcribe(blob) {
  busy = true; controls();
  resultText = ''; $('transcript').hidden = true; $('empty').hidden = false;
  $('copy').disabled = true; $('details').hidden = true; $('result-meta').hidden = true;
  if (playbackUrl) URL.revokeObjectURL(playbackUrl);
  playbackUrl = URL.createObjectURL(blob); $('audio').src = playbackUrl; saveAudio.href = playbackUrl; $('playback').hidden = false;
  $('record-label').textContent = 'Transcribing your recording…'; $('result-state').textContent = 'Listening to the details…';
  message('Processing locally. The first request loads the speech model and can take longer.');
  try {
    if (blob.size > 25 * 1024 * 1024) throw new Error('Choose a WAV file smaller than 25 MB.');
    const form = new FormData(); form.append('file', blob, 'recording.wav');
    const data = await api('/api/transcribe', {method:'POST', body:form});
    resultText = data.text; $('transcript').textContent = data.text;
    $('empty').hidden = true; $('transcript').hidden = false; $('copy').disabled = false;
    $('raw').textContent = data.joins?.length ? data.segments.map(s => `${s.start.toFixed(1)}–${s.end.toFixed(1)} s\n${s.raw}`).join('\n\n') : data.raw_text;
    $('details').hidden = false; $('result-meta').hidden = false;
    $('word-count').textContent = `${data.words.length} words · ${data.duration.toFixed(1)} seconds`;
    $('result-state').textContent = 'Ready to review';
    const review = (data.warnings || []).filter(w => w.startsWith('Review '));
    message(review.length ? `Transcript ready, with joins to check. ${review.join(' ')}` : 'Your transcript is ready. Listen back to check the endings; no accuracy score has been established yet.');
  } catch (error) { message(error.message, true); $('result-state').textContent = 'Recording needs attention'; }
  finally { busy = false; $('record-label').textContent = 'Tap to record again'; controls(); status(); }
}
$('mic').addEventListener('click', () => recording ? stop() : start());
$('upload').addEventListener('change', event => { const file = event.target.files[0]; if (file) acceptRecording(file); event.target.value = ''; });
$('copy').addEventListener('click', async () => { try { await navigator.clipboard.writeText(resultText); message('Transcript copied.'); } catch { message('Copy was unavailable. Select and copy the transcript directly.', true); } });
$('download').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([resultText], {type:'text/plain;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = 'sawt-transcript.txt'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('prepare').addEventListener('click', async () => {
  busy = true; controls(); message('Loading the speech model. The first load downloads its weights.');
  try { await api('/api/prepare', {method:'POST'}); message('The speech model is ready. You can start recording.'); }
  catch (error) { message(error.message, true); }
  finally { busy = false; controls(); status(); }
});
window.addEventListener('pagehide', () => { stream?.getTracks().forEach(t => t.stop()); });
draw(); status(); setInterval(status, 5000);
