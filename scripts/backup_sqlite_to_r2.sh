#!/usr/bin/env bash

set -Eeuo pipefail

umask 077

R2_BACKUP_ENV_FILE="${R2_BACKUP_ENV_FILE:-/opt/tradeTracker/tradeTracker/.env}"

if [[ -f "$R2_BACKUP_ENV_FILE" ]]; then
    # Read only known keys; unlike sourcing, this supports dotenv spacing without
    # executing arbitrary contents from the application's environment file.
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?(DB_PATH|R2_ENDPOINT|R2_KEY_ID|R2_API_KEY|R2_BUCKET|R2_PREFIX)[[:space:]]*=(.*)$ ]]; then
            key="${BASH_REMATCH[2]}"
            value="${BASH_REMATCH[3]}"

            # Values supplied directly to cron or the shell take precedence.
            if [[ -v "$key" ]]; then
                continue
            fi

            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            if [[ ${#value} -ge 2 ]]; then
                first_character="${value:0:1}"
                last_character="${value: -1}"
                if [[ "$first_character" == "$last_character" && ( "$first_character" == "'" || "$first_character" == '"' ) ]]; then
                    value="${value:1:${#value}-2}"
                fi
            fi

            printf -v "$key" '%s' "$value"
            export "$key"
        fi
    done < "$R2_BACKUP_ENV_FILE"
fi

DB_PATH="${DB_PATH:-/opt/tradeTracker/data/tradeTracker.sqlite}"
R2_BUCKET="${R2_BUCKET:-tradetracker}"
R2_PREFIX="${R2_PREFIX:-backups/sqlite}"

: "${R2_ENDPOINT:?Set R2_ENDPOINT in the environment or $R2_BACKUP_ENV_FILE}"
: "${R2_KEY_ID:?Set R2_KEY_ID in the environment or $R2_BACKUP_ENV_FILE}"
: "${R2_API_KEY:?Set R2_API_KEY in the environment or $R2_BACKUP_ENV_FILE}"
: "${R2_BUCKET:?Set R2_BUCKET in the environment or $R2_BACKUP_ENV_FILE}"

for command in sqlite3 gzip aws stat; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$command" >&2
        exit 1
    fi
done

if [[ ! -r "$DB_PATH" ]]; then
    printf 'SQLite database is not readable: %s\n' "$DB_PATH" >&2
    exit 1
fi

work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT

timestamp="$(date -u +'%Y-%m-%dT%H-%M-%SZ')"
backup_name="tradeTracker-${timestamp}.sqlite"
backup_path="${work_dir}/${backup_name}"
archive_path="${backup_path}.gz"
object_key="${R2_PREFIX%/}/${backup_name}.gz"

# .backup produces a transactionally consistent snapshot while the app is running.
sqlite3 -cmd '.timeout 30000' "$DB_PATH" ".backup '$backup_path'"

integrity_result="$(sqlite3 "$backup_path" 'PRAGMA quick_check;')"
if [[ "$integrity_result" != "ok" ]]; then
    printf 'SQLite integrity check failed: %s\n' "$integrity_result" >&2
    exit 1
fi

gzip -9 "$backup_path"

export AWS_ACCESS_KEY_ID="$R2_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_API_KEY"
export AWS_DEFAULT_REGION=auto
export AWS_EC2_METADATA_DISABLED=true

aws --endpoint-url "$R2_ENDPOINT" s3 cp \
    "$archive_path" "s3://${R2_BUCKET}/${object_key}" \
    --only-show-errors

local_size="$(stat -c '%s' "$archive_path")"
remote_size="$(aws --endpoint-url "$R2_ENDPOINT" s3api head-object \
    --bucket "$R2_BUCKET" \
    --key "$object_key" \
    --query 'ContentLength' \
    --output text)"

if [[ "$remote_size" != "$local_size" ]]; then
    printf 'Upload verification failed: local size %s, remote size %s\n' \
        "$local_size" "$remote_size" >&2
    exit 1
fi

printf 'Backup uploaded to r2://%s/%s (%s bytes)\n' \
    "$R2_BUCKET" "$object_key" "$local_size"
