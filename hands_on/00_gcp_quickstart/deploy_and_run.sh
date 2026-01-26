gcloud run jobs deploy job-quickstart \
    --source . \
    --tasks 1 \
    --max-retries 5 \
    --region europe-west1	 \
    --project=leon-test-485022
    # --set-env-vars SLEEP_MS=10000 \
    # --set-env-vars FAIL_RATE=0.1 \

gcloud run jobs execute job-quickstart