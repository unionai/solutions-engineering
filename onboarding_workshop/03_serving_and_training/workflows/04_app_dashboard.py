"""
Chapter 4b — Serve an interactive dashboard
===========================================
The same `review-classifier`, this time behind a Streamlit UI you can click
through — paste a review, get a live sentiment prediction.

What this chapter shows:

- Non-FastAPI app:  an `AppEnvironment` + `@env.server` can run *any* web server
                    (here Streamlit as a subprocess) — apps are framework-agnostic.
- Same artifact:    the dashboard mounts the very same `review-classifier`
                    Artifact as the API, so both services serve one pinned model.

Deploy it:
  uv run flyte serve 04_app_dashboard.py app_env      # prints the app URL
Then open the URL in a browser.
"""

import flyte
import flyte.io
from flyte.app import ArtifactValue, Parameter

image = flyte.Image.from_debian_base().with_pip_packages("streamlit", "scikit-learn")

app_env = flyte.app.AppEnvironment(
    name="review-radar-dashboard",
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    port=8080,
    requires_auth=False,
    scaling=flyte.app.Scaling(replicas=(1, 1)),
    parameters=[
        Parameter(name="model", value=ArtifactValue(name="review-classifier", type="file"), download=True),
    ],
)

# The Streamlit UI, written to a file and launched by the server hook below.
STREAMLIT_SCRIPT = '''
import os, pickle
import streamlit as st

st.set_page_config(page_title="Review Radar", page_icon="📝")
st.title("📝 Review Radar")
st.caption("Live sentiment scoring — served on Union, powered by the review-classifier Artifact.")

@st.cache_resource
def load_model():
    with open(os.environ["MODEL_PATH"], "rb") as f:
        return pickle.load(f)

model = load_model()
text = st.text_area("Paste a product review:", "This product is amazing, I love it!")
if st.button("Classify") and text.strip():
    label = str(model.predict([text])[0])
    conf = float(model.predict_proba([text]).max())
    st.metric("Prediction", label.upper(), f"{conf:.1%} confidence")
'''


@app_env.server
def serve(model: flyte.io.File) -> None:
    """Write the Streamlit script and launch it, pointing at the mounted model."""
    import os
    import subprocess

    os.environ["MODEL_PATH"] = model.path
    with open("/tmp/_dashboard.py", "w") as f:
        f.write(STREAMLIT_SCRIPT)
    subprocess.run(
        [
            "streamlit", "run", "/tmp/_dashboard.py",
            "--server.port", "8080",
            "--server.address", "0.0.0.0",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        check=False,
    )


if __name__ == "__main__":
    flyte.init_from_config()
    served = flyte.serve(app_env)
    print(served.url)
