
import ollama

MODEL_NAME = "qwen2.5:3b"

# Keep failures bounded, and avoid a long model reload between chat turns.
client = ollama.Client(
    host="http://localhost:11434",
    timeout=180.0
)


def generate_response( prompt, temperature=0.2, on_token=None, num_predict=800):
    """
    Generate an answer using the local Ollama model.
    """

    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": num_predict,
            },
            keep_alive="30m",
            stream=True,
        )

        chunks = []
        last_chunk = {}
        for chunk in response:
            last_chunk = chunk
            token = chunk.get("message", {}).get("content", "")
            if token:
                chunks.append(token)
                if on_token is not None:
                    on_token(token)

        if on_token is None and last_chunk:
            print("\n--- Ollama Generation Info ---")
            print("Done reason:", last_chunk.get("done_reason"))
            print("Prompt tokens:", last_chunk.get("prompt_eval_count"))
            print("Generated tokens:", last_chunk.get("eval_count"))
            print("Done:", last_chunk.get("done"))

        return "".join(chunks).strip()

    except Exception as error:
        print(f"Ollama error: {type(error).__name__}: {error}")
        return "Sorry, I couldn't generate a response right now."
