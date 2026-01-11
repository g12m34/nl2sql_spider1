#!/bin/bash
# Background watcher for Anthropic batch job
BATCH_ID="$1"
POLL_INTERVAL="${2:-30}"
LOG_FILE="/workspace/project/evaluation/batch_jobs/watcher_anthropic_${BATCH_ID}.log"

echo "$(date): Starting watcher for $BATCH_ID" > "$LOG_FILE"
echo "Poll interval: ${POLL_INTERVAL}s" >> "$LOG_FILE"

while true; do
    STATUS=$(python /workspace/project/scripts/anthropic_batch.py status "$BATCH_ID" 2>&1)
    PROC_STATUS=$(echo "$STATUS" | grep "Status:" | head -1 | cut -d: -f2 | xargs)
    SUCCEEDED=$(echo "$STATUS" | grep "Succeeded:" | head -1 | grep -oP '\d+' | head -1)
    
    echo "$(date): Status = $PROC_STATUS, Succeeded = $SUCCEEDED" >> "$LOG_FILE"
    
    if [[ "$PROC_STATUS" == "ended" ]]; then
        echo "$(date): JOB COMPLETED!" >> "$LOG_FILE"
        # Fetch results
        python /workspace/project/scripts/anthropic_batch.py results "$BATCH_ID" >> "$LOG_FILE" 2>&1
        echo "$(date): Results saved." >> "$LOG_FILE"
        
        # Create completion marker
        touch "/workspace/project/evaluation/batch_jobs/COMPLETED_anthropic_${BATCH_ID}"
        break
    fi
    
    sleep $POLL_INTERVAL
done
