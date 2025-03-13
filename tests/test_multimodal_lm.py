from typing import Union

import pytest
import torch
from torch import Tensor, nn

from mfai.tokenizers import GPT2Tokenizer, LlamaTokenizer, MiniTokenizer
from mfai.torch.models.llms.multimodal import MultiModalLM, MultiModalLMSettings
from mfai.torch.namedtensor import NamedTensor


def generate_text_simple(
    model: nn.Module,
    idx: Tensor,
    max_new_tokens: int,
    context_size: int,
    vision_input: Union[None, NamedTensor] = None,
) -> Tensor:
    # idx is (B, T) array of indices in the current context
    for _ in range(max_new_tokens):
        # Crop current context if it exceeds the supported context size
        # E.g., if LLM supports only 5 tokens, and the context size is 10
        # then only the last 5 tokens are used as context
        idx_cond = idx[:, -context_size:]

        # Get the predictions
        with torch.no_grad():
            if vision_input:
                logits = model(idx_cond, vision_input)
            else:
                logits = model(idx_cond)

        # Focus only on the last time step
        # (batch, n_token, vocab_size) becomes (batch, vocab_size)
        logits = logits[:, -1, :]

        # Get the idx of the vocab entry with the highest logits value
        idx_next = torch.argmax(logits, dim=-1, keepdim=True)  # (batch, 1)

        # Append sampled index to the running sequence
        idx = torch.cat((idx, idx_next), dim=1)  # (batch, n_tokens+1)

    return idx


@pytest.mark.parametrize(
    "backend_target",
    [
        (
            "llama2",
            {
                "llama": "Sustine et abstine staff пописа sur Datenrefref equations Soundantalfs",
                "gpt2": "Sustine et abstine objections Sanskrit hormavin 25 noting carbs contamination chatting caramel",
                "mini_gpt2": "Sustine et abstinelined regener cannabinoidibus fictional makeshift Literary Abdullah Tree dozens",
            },
        ),
        (
            "gpt2",
            {
                "llama": "Sustine et abstinerefrefrefумrefnakeжёнfragmentrefwhy",
                "gpt2": "Sustine et abstineohoorphLE updates� Oaks GD straight correlates Sir",
                "mini_gpt2": "Sustine et abstine200 Qi heter Wallace revolution 1997 349ety PARK682",
            },
        ),
    ],
)
def test_multimodal_llm(backend_target):
    torch.manual_seed(999)
    backend, target = backend_target
    for tokenizer in [
        LlamaTokenizer(),
        GPT2Tokenizer(),
        MiniTokenizer(GPT2Tokenizer()),
    ]:
        model = MultiModalLM(
            settings=MultiModalLMSettings(
                vision_input_shape=(3, 3, 2, 1),
                backend=backend,
                n_heads=1,
                n_layers=1,
                emb_dim=32,
                hidden_dim=32,
                context_length=32,
            )
        )
        vision_input = NamedTensor(
            torch.randn(1, 3, 3, 2, 1),
            names=("batch", "lat", "lon", "timestep", "features"),
            feature_names=("u",),
        )
        encoded = tokenizer.encode("Sustine et abstine")
        encoded_tensor = torch.tensor(encoded).unsqueeze(0)

        out = generate_text_simple(
            model=model,
            idx=encoded_tensor,
            max_new_tokens=10,
            context_size=model.context_length,
            vision_input=vision_input,
        )
        out = torch.where(out > tokenizer.vocab_size - 1, 999, out)
        decoded_text = tokenizer.decode(out.squeeze(0).tolist())

        assert decoded_text == target[tokenizer.name()]
