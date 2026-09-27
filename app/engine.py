import os
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('HF_HOME', str(ROOT / '.cache' / 'huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
MODEL_ID = 'NAMAA-Space/Cohere-Speech-Tashkeel-2B'
REVISION = '710704bf787fa3c27f7567aa08078861925aeee2'


class SpeechEngine:
    def __init__(self):
        self.lock = Lock()
        self.model = None
        self.processor = None
        self.state = 'not_loaded'
        self.error = None
        self.device = None

    def load(self):
        if self.model is not None:
            return
        self.state, self.error = 'loading', None
        try:
            import torch
            from transformers import AutoProcessor, CohereAsrForConditionalGeneration
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.dtype = torch.bfloat16 if self.device == 'cuda' else torch.float32
            snapshot = Path(os.environ['HF_HOME']) / 'hub' / ('models--' + MODEL_ID.replace('/', '--')) / 'snapshots' / REVISION
            # Fully downloaded installations must also work without a network.
            source = str(snapshot) if (snapshot / 'model.safetensors').exists() else MODEL_ID
            self.processor = AutoProcessor.from_pretrained(source, revision=REVISION)
            model = CohereAsrForConditionalGeneration.from_pretrained(
                source, revision=REVISION, dtype=self.dtype,
                attn_implementation='sdpa',
                device_map=self.device,
            ).eval()
            self.model = model
            self.state = 'ready'
        except Exception as exc:
            self.state, self.error = 'error', str(exc)
            raise

    def transcribe(self, audio):
        import torch
        self.load()
        features = self.processor.feature_extractor(
            [audio], sampling_rate=16000, return_tensors='pt',
            padding='longest', return_attention_mask=True,
        )
        chunk_index = features.pop('audio_chunk_index')
        prompt = self.processor.get_decoder_prompt_ids(language='ar', punctuation=True)
        with torch.inference_mode():
            output = self.model.generate(
                input_features=features['input_features'].to(self.device, self.dtype),
                attention_mask=features['attention_mask'].to(self.device),
                decoder_input_ids=torch.tensor([prompt], dtype=torch.long, device=self.device),
                max_new_tokens=448, do_sample=False,
            )
        # Reject truncated output instead of silently dropping the end of a paragraph.
        eos = self.model.generation_config.eos_token_id
        eos_ids = eos if isinstance(eos, list) else [eos]
        if output[0, -1].item() not in eos_ids:
            raise ValueError('The decoder reached its output limit. Please use shorter sentences.')
        result = self.processor.decode(output, skip_special_tokens=True,
                                       audio_chunk_index=chunk_index, language='ar')
        if isinstance(result, list):
            result = ' '.join(result)
        if not isinstance(result, str):
            raise RuntimeError('Unexpected output from the speech model.')
        return result.strip()


engine = SpeechEngine()
