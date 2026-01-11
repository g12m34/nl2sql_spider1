#!/bin/bash
# Background watcher for Gemini batch job
JOB_NAME="$1"
POLL_INTERVAL="${2:-30}"
LOG_FILE="/workspace/project/evaluation/batch_jobs/watcher_$(echo $JOB_NAME | tr '/' '_').log"

echo "$(date): Starting watcher for $JOB_NAME" > "$LOG_FILE"
echo "Poll interval: ${POLL_INTERVAL}s" >> "$LOG_FILE"

while true; do
    STATUS=$(python /workspace/project/scripts/gemini_batch.py status "$JOB_NAME" 2>&1)
    STATE=$(echo "$STATUS" | grep "State:" | cut -d: -f2 | xargs)
    
    echo "$(date): State = $STATE" >> "$LOG_FILE"
    
    if [[ "$STATE" == *"SUCCEEDED"* ]]; then
        echo "$(date): JOB COMPLETED SUCCESSFULLY!" >> "$LOG_FILE"
        # Fetch results
        python /workspace/project/scripts/gemini_batch.py results "$JOB_NAME" >> "$LOG_FILE" 2>&1
        echo "$(date): Results saved. Run 'python gemini_batch.py evaluate' to evaluate." >> "$LOG_FILE"
        
        # Create completion marker
        touch "/workspace/project/evaluation/batch_jobs/COMPLETED_$(echo $JOB_NAME | tr '/' '_')"
        break
    elif [[ "$STATE" == *"FAILED"* ]] || [[ "$STATE" == *"CANCELLED"* ]] || [[ "$STATE" == *"EXPIRED"* ]]; then
        echo "$(date): JOB FAILED with state: $STATE" >> "$LOG_FILE"
        touch "/workspace/project/evaluation/batch_jobs/FAILED_$(echo $JOB_NAME | tr '/' '_')"
        break
    fi
    
    sleep $POLL_INTERVAL
done
