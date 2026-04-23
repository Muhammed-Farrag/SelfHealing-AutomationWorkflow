export type FailureClass = 'timeout' | 'http_error' | 'missing_file' | 'missing_column' | 'missing_db';
export type EpisodeStatus = 'pending' | 'applied' | 'rejected' | 'dry_run' | 'in_progress';
export type PlanStatus = 'pending' | 'applied' | 'rejected' | 'dry_run';
export type ActionOperator = 'set_env' | 'set_retry' | 'set_timeout' | 'replace_path' | 'add_precheck';

export const FAILURE_CLASS_COLORS: Record<FailureClass, string> = {
  timeout: '#f59e0b',
  http_error: '#ef4444',
  missing_file: '#3b82f6',
  missing_column: '#8b5cf6',
  missing_db: '#f97316',
};

export const STATUS_COLORS: Record<PlanStatus | EpisodeStatus, string> = {
  pending: '#f59e0b',
  applied: '#10b981',
  rejected: '#ef4444',
  dry_run: '#3b82f6',
  in_progress: '#f59e0b',
};

export interface Episode {
  id: string;
  dag: string;
  task: string;
  failureClass: FailureClass;
  confidence: number;
  mlAgrees: boolean;
  regexAgrees: boolean;
  status: EpisodeStatus;
  timestamp: string;
  logExcerpt: string;
  drainTemplate: string;
  faissMatches: { score: number; text: string }[];
}

export interface RepairAction {
  operator: ActionOperator;
  param: string;
  newValue: string;
  justification: string;
}

export interface RepairPlan {
  id: string;
  episodeId: string;
  failureClass: FailureClass;
  confidence: number;
  reasoning: string;
  actions: RepairAction[];
  requiresHuman: boolean;
  status: PlanStatus;
  timestamp: string;
  diffOld: string[];
  diffNew: string[];
  diffFile: string;
}

export interface AuditEvent {
  id: string;
  type: 'failure_detected' | 'plan_generated' | 'patch_applied' | 'human_approved' | 'rollback_executed';
  description: string;
  entityId: string;
  timestamp: string;
  commitHash?: string;
  dag?: string;
}

export interface PatchRecord {
  id: string;
  planId: string;
  fileModified: string;
  appliedAt: string;
  commitHash: string;
  status: 'applied' | 'rolled_back';
}

export const EPISODES: Episode[] = [
  {
    id: 'ep_001',
    dag: 'data_ingestion_v3',
    task: 'fetch_external_api',
    failureClass: 'timeout',
    confidence: 0.97,
    mlAgrees: true,
    regexAgrees: true,
    status: 'applied',
    timestamp: '2026-04-23T08:14:32Z',
    logExcerpt: `[2026-04-23 08:14:29] INFO  - Starting task fetch_external_api
[2026-04-23 08:14:29] INFO  - Connecting to https://api.datavendor.io/v2/stream
[2026-04-23 08:14:59] ERROR - requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.datavendor.io', port=443): Read timed out. (read timeout=30)
[2026-04-23 08:14:59] ERROR - Timeout after 30s waiting for response
[2026-04-23 08:14:59] CRITICAL - Task failed with exception: ReadTimeout
[2026-04-23 08:14:59] INFO  - Marking task as FAILED`,
    drainTemplate: 'requests.exceptions.ReadTimeout: HTTPSConnectionPool(host=<*>, port=<*>): Read timed out. (read timeout=<*>)',
    faissMatches: [
      { score: 0.94, text: 'DAG data_sync: Set timeout=120s for external API calls to datavendor.io' },
      { score: 0.87, text: 'Increase HTTP read timeout when API latency exceeds 30s threshold' },
      { score: 0.79, text: 'Add retry logic with exponential backoff for timeout errors' },
    ],
  },
  {
    id: 'ep_002',
    dag: 'ml_pipeline_prod',
    task: 'load_training_data',
    failureClass: 'missing_file',
    confidence: 0.91,
    mlAgrees: true,
    regexAgrees: true,
    status: 'applied',
    timestamp: '2026-04-23T07:55:10Z',
    logExcerpt: `[2026-04-23 07:55:08] INFO  - Starting task load_training_data
[2026-04-23 07:55:08] INFO  - Loading dataset from /data/raw/training_2026_q1.parquet
[2026-04-23 07:55:08] ERROR - FileNotFoundError: [Errno 2] No such file or directory: '/data/raw/training_2026_q1.parquet'
[2026-04-23 07:55:08] ERROR - Expected file at path /data/raw/training_2026_q1.parquet
[2026-04-23 07:55:08] CRITICAL - Cannot proceed without training data`,
    drainTemplate: 'FileNotFoundError: [Errno 2] No such file or directory: <*>',
    faissMatches: [
      { score: 0.96, text: 'Update data path to /mnt/storage/training/ when Q1 data moves' },
      { score: 0.88, text: 'Add path existence precheck before loading parquet files' },
      { score: 0.72, text: 'Use dynamic date-based path resolution for quarterly datasets' },
    ],
  },
  {
    id: 'ep_003',
    dag: 'reporting_daily',
    task: 'export_to_postgres',
    failureClass: 'missing_db',
    confidence: 0.88,
    mlAgrees: true,
    regexAgrees: false,
    status: 'pending',
    timestamp: '2026-04-23T07:31:45Z',
    logExcerpt: `[2026-04-23 07:31:43] INFO  - Starting task export_to_postgres
[2026-04-23 07:31:43] INFO  - Connecting to postgres://prod-db.internal:5432/reports
[2026-04-23 07:31:44] ERROR - psycopg2.OperationalError: could not connect to server: Connection refused
[2026-04-23 07:31:44] ERROR - Is the server running on host 'prod-db.internal' and accepting TCP/IP connections on port 5432?
[2026-04-23 07:31:44] CRITICAL - Database connection failed after 3 retries`,
    drainTemplate: 'psycopg2.OperationalError: could not connect to server: Connection refused on host=<*> port=<*>',
    faissMatches: [
      { score: 0.91, text: 'Update DB_HOST env var when prod-db migrates to new cluster' },
      { score: 0.83, text: 'Add connection pool retry with max_attempts=5 for DB outages' },
      { score: 0.76, text: 'Fallback to replica DB when primary connection fails' },
    ],
  },
  {
    id: 'ep_004',
    dag: 'etl_transform_v2',
    task: 'normalize_schema',
    failureClass: 'missing_column',
    confidence: 0.94,
    mlAgrees: true,
    regexAgrees: true,
    status: 'pending',
    timestamp: '2026-04-23T06:48:22Z',
    logExcerpt: `[2026-04-23 06:48:20] INFO  - Starting task normalize_schema
[2026-04-23 06:48:20] INFO  - Loading dataframe from upstream task
[2026-04-23 06:48:21] ERROR - KeyError: 'customer_segment'
[2026-04-23 06:48:21] ERROR - Column 'customer_segment' not found in DataFrame
[2026-04-23 06:48:21] ERROR - Available columns: ['customer_id', 'order_date', 'revenue', 'region']
[2026-04-23 06:48:21] CRITICAL - Schema validation failed`,
    drainTemplate: "KeyError: <*> — Column <*> not found in DataFrame. Available columns: <*>",
    faissMatches: [
      { score: 0.93, text: 'Add customer_segment column derivation step before normalize_schema' },
      { score: 0.85, text: 'Map customer_type → customer_segment in upstream fetch_customers task' },
      { score: 0.71, text: 'Add schema validation precheck with expected column list' },
    ],
  },
  {
    id: 'ep_005',
    dag: 'data_ingestion_v3',
    task: 'validate_response',
    failureClass: 'http_error',
    confidence: 0.99,
    mlAgrees: true,
    regexAgrees: true,
    status: 'applied',
    timestamp: '2026-04-23T06:21:07Z',
    logExcerpt: `[2026-04-23 06:21:05] INFO  - Starting task validate_response
[2026-04-23 06:21:05] INFO  - GET https://api.datavendor.io/v2/health
[2026-04-23 06:21:06] ERROR - HTTP 503 Service Unavailable
[2026-04-23 06:21:06] ERROR - Response body: {"error": "upstream_timeout", "retry_after": 60}
[2026-04-23 06:21:06] CRITICAL - API returned non-2xx status code: 503`,
    drainTemplate: 'HTTP <*> <*> — Response: {"error": "<*>", "retry_after": <*>}',
    faissMatches: [
      { score: 0.97, text: 'Implement exponential backoff for 5xx errors on datavendor.io API' },
      { score: 0.89, text: 'Add 503 to retryable status codes list in HTTP operator config' },
      { score: 0.81, text: 'Set retry_delay=retry_after header value when present' },
    ],
  },
  {
    id: 'ep_006',
    dag: 'feature_store_sync',
    task: 'compute_embeddings',
    failureClass: 'timeout',
    confidence: 0.83,
    mlAgrees: false,
    regexAgrees: true,
    status: 'dry_run',
    timestamp: '2026-04-23T05:55:33Z',
    logExcerpt: `[2026-04-23 05:55:30] INFO  - Starting task compute_embeddings
[2026-04-23 05:55:30] INFO  - Processing batch of 50000 records
[2026-04-23 05:55:30] INFO  - Sending to embedding service at gpu-cluster-02:8080
[2026-04-23 06:05:30] ERROR - socket.timeout: timed out after 600s
[2026-04-23 06:05:30] CRITICAL - Embedding computation exceeded timeout`,
    drainTemplate: 'socket.timeout: timed out after <*>s during batch processing of <*> records',
    faissMatches: [
      { score: 0.88, text: 'Increase execution_timeout to 1800s for large embedding batches' },
      { score: 0.82, text: 'Split batch into chunks of 10000 to reduce per-request latency' },
      { score: 0.74, text: 'Enable async embedding with callback URL for long-running jobs' },
    ],
  },
  {
    id: 'ep_007',
    dag: 'user_activity_etl',
    task: 'load_clickstream',
    failureClass: 'missing_file',
    confidence: 0.76,
    mlAgrees: true,
    regexAgrees: false,
    status: 'rejected',
    timestamp: '2026-04-23T05:10:18Z',
    logExcerpt: `[2026-04-23 05:10:15] INFO  - Starting task load_clickstream
[2026-04-23 05:10:16] INFO  - Scanning s3://prod-logs/clickstream/2026/04/23/
[2026-04-23 05:10:17] ERROR - botocore.exceptions.ClientError: NoSuchKey
[2026-04-23 05:10:17] ERROR - The specified key does not exist: s3://prod-logs/clickstream/2026/04/23/events_00.parquet
[2026-04-23 05:10:18] CRITICAL - S3 object not found`,
    drainTemplate: 'botocore.exceptions.ClientError: NoSuchKey — s3://<*>/<*>',
    faissMatches: [
      { score: 0.89, text: 'Add S3 key existence check before loading clickstream data' },
      { score: 0.84, text: 'Use SLA-based wait sensor for late-arriving S3 data' },
      { score: 0.69, text: 'Fallback to previous day data when current day files missing' },
    ],
  },
  {
    id: 'ep_008',
    dag: 'reporting_daily',
    task: 'send_alerts',
    failureClass: 'http_error',
    confidence: 0.95,
    mlAgrees: true,
    regexAgrees: true,
    status: 'applied',
    timestamp: '2026-04-23T04:30:55Z',
    logExcerpt: `[2026-04-23 04:30:52] INFO  - Starting task send_alerts
[2026-04-23 04:30:53] INFO  - POST https://hooks.slack.com/services/T0X.../
[2026-04-23 04:30:54] ERROR - HTTP 429 Too Many Requests
[2026-04-23 04:30:54] ERROR - Retry-After: 3600
[2026-04-23 04:30:55] CRITICAL - Slack webhook rate limited`,
    drainTemplate: 'HTTP 429 Too Many Requests — Retry-After: <*>',
    faissMatches: [
      { score: 0.95, text: 'Add rate limit handling with Retry-After header for Slack webhook' },
      { score: 0.87, text: 'Implement message queue to batch Slack notifications' },
      { score: 0.79, text: 'Add exponential backoff for 429 responses on webhook calls' },
    ],
  },
];

export const REPAIR_PLANS: RepairPlan[] = [
  {
    id: 'plan_ep_001',
    episodeId: 'ep_001',
    failureClass: 'timeout',
    confidence: 0.97,
    reasoning: 'ML classifier and regex both agree this is a network timeout in an external API call. Historical playbook shows increasing the read timeout from 30s to 120s resolves this class of failure. The vendor API is known to have high latency during peak hours (08:00–10:00 UTC).',
    actions: [
      {
        operator: 'set_timeout',
        param: 'http_conn_id.read_timeout',
        newValue: '120',
        justification: 'Extend read timeout from 30s to 120s to accommodate vendor API latency spikes',
      },
      {
        operator: 'set_retry',
        param: 'retries',
        newValue: '3',
        justification: 'Add 3 retries to handle transient timeouts automatically',
      },
      {
        operator: 'set_env',
        param: 'VENDOR_API_TIMEOUT',
        newValue: '120',
        justification: 'Update environment variable to propagate timeout change to all tasks',
      },
    ],
    requiresHuman: false,
    status: 'applied',
    timestamp: '2026-04-23T08:15:01Z',
    diffFile: 'dags/data_ingestion_v3.py',
    diffOld: [
      "    http_conn_id='datavendor_default',",
      "    timeout=30,",
      "    retries=0,",
      "    retry_delay=timedelta(minutes=1),",
      "    method='GET',",
    ],
    diffNew: [
      "    http_conn_id='datavendor_default',",
      "    timeout=120,",
      "    retries=3,",
      "    retry_delay=timedelta(minutes=2),",
      "    method='GET',",
    ],
  },
  {
    id: 'plan_ep_002',
    episodeId: 'ep_002',
    failureClass: 'missing_file',
    confidence: 0.91,
    reasoning: 'File path /data/raw/training_2026_q1.parquet does not exist. The quarterly data rotation moved files to /mnt/storage/training/. Adding a path precheck and updating the base path will resolve this failure class. Requires human review due to filesystem path change.',
    actions: [
      {
        operator: 'replace_path',
        param: 'data_path',
        newValue: '/mnt/storage/training/training_2026_q1.parquet',
        justification: 'Update data path to new storage mount location after Q1 data migration',
      },
      {
        operator: 'add_precheck',
        param: 'path_exists_sensor',
        newValue: 'True',
        justification: 'Add file existence sensor before data load to surface missing files early',
      },
    ],
    requiresHuman: true,
    status: 'applied',
    timestamp: '2026-04-23T07:55:45Z',
    diffFile: 'dags/ml_pipeline_prod.py',
    diffOld: [
      "DATA_PATH = '/data/raw/training_2026_q1.parquet'",
      "",
      "load_data = PythonOperator(",
      "    task_id='load_training_data',",
      "    python_callable=load_parquet,",
    ],
    diffNew: [
      "DATA_PATH = '/mnt/storage/training/training_2026_q1.parquet'",
      "",
      "check_file = FileSensor(",
      "    task_id='check_data_exists',",
      "    filepath=DATA_PATH,",
      "    poke_interval=60,",
      ")",
      "",
      "load_data = PythonOperator(",
      "    task_id='load_training_data',",
      "    python_callable=load_parquet,",
    ],
  },
  {
    id: 'plan_ep_003',
    episodeId: 'ep_003',
    failureClass: 'missing_db',
    confidence: 0.88,
    reasoning: 'Database connection refused on prod-db.internal:5432. Infrastructure team migrated PostgreSQL to new cluster prod-db-v2.internal. Updating DB_HOST environment variable and adding connection retry logic will restore connectivity.',
    actions: [
      {
        operator: 'set_env',
        param: 'DB_HOST',
        newValue: 'prod-db-v2.internal',
        justification: 'Update database host after cluster migration from prod-db to prod-db-v2',
      },
      {
        operator: 'set_retry',
        param: 'connect_retries',
        newValue: '5',
        justification: 'Add 5 connection retries with backoff for transient DB unavailability',
      },
    ],
    requiresHuman: true,
    status: 'pending',
    timestamp: '2026-04-23T07:32:10Z',
    diffFile: 'dags/reporting_daily.py',
    diffOld: [
      "    conn_id='postgres_prod',",
      "    database='reports',",
      "    # host: prod-db.internal",
      "    connect_timeout=5,",
    ],
    diffNew: [
      "    conn_id='postgres_prod_v2',",
      "    database='reports',",
      "    # host: prod-db-v2.internal",
      "    connect_timeout=10,",
      "    connect_retries=5,",
    ],
  },
  {
    id: 'plan_ep_004',
    episodeId: 'ep_004',
    failureClass: 'missing_column',
    confidence: 0.94,
    reasoning: 'Column customer_segment missing from DataFrame. Upstream task fetch_customers renamed the column to customer_type in schema v2.3. Adding a column mapping transformation before normalize_schema will resolve the KeyError without upstream changes.',
    actions: [
      {
        operator: 'add_precheck',
        param: 'schema_validator',
        newValue: 'True',
        justification: 'Add schema validation step to catch missing columns before processing',
      },
      {
        operator: 'replace_path',
        param: 'column_map.customer_type',
        newValue: 'customer_segment',
        justification: 'Remap customer_type → customer_segment to match downstream schema expectations',
      },
    ],
    requiresHuman: true,
    status: 'pending',
    timestamp: '2026-04-23T06:48:58Z',
    diffFile: 'dags/etl_transform_v2.py',
    diffOld: [
      "def normalize_schema(df):",
      "    segment = df['customer_segment']",
      "    return df.assign(segment=segment)",
    ],
    diffNew: [
      "COLUMN_MAP = {'customer_type': 'customer_segment'}",
      "",
      "def normalize_schema(df):",
      "    df = df.rename(columns=COLUMN_MAP)",
      "    segment = df['customer_segment']",
      "    return df.assign(segment=segment)",
    ],
  },
  {
    id: 'plan_ep_005',
    episodeId: 'ep_005',
    failureClass: 'http_error',
    confidence: 0.99,
    reasoning: 'HTTP 503 from vendor API health endpoint with retry_after=60. Adding 503 to retryable status codes and implementing exponential backoff will handle transient upstream outages automatically.',
    actions: [
      {
        operator: 'set_retry',
        param: 'retries',
        newValue: '5',
        justification: 'Set 5 retries to handle vendor API outages lasting up to 5 minutes',
      },
      {
        operator: 'set_env',
        param: 'RETRYABLE_STATUS_CODES',
        newValue: '429,500,502,503,504',
        justification: 'Add 503 to retryable status code list for automatic retry logic',
      },
    ],
    requiresHuman: false,
    status: 'applied',
    timestamp: '2026-04-23T06:21:40Z',
    diffFile: 'dags/data_ingestion_v3.py',
    diffOld: [
      "    retries=2,",
      "    retry_delay=timedelta(seconds=30),",
      "    # RETRYABLE_STATUS_CODES: 429,500",
    ],
    diffNew: [
      "    retries=5,",
      "    retry_delay=timedelta(seconds=60),",
      "    # RETRYABLE_STATUS_CODES: 429,500,502,503,504",
    ],
  },
  {
    id: 'plan_ep_008',
    episodeId: 'ep_008',
    failureClass: 'http_error',
    confidence: 0.95,
    reasoning: 'Slack webhook returning HTTP 429 (rate limited) with Retry-After: 3600. Implementing message queuing and honoring the Retry-After header will prevent future rate limit violations.',
    actions: [
      {
        operator: 'set_retry',
        param: 'retry_delay',
        newValue: '3600',
        justification: 'Honor Retry-After: 3600 header from Slack webhook rate limit response',
      },
      {
        operator: 'set_env',
        param: 'SLACK_BATCH_MODE',
        newValue: 'true',
        justification: 'Enable message batching to reduce webhook call frequency by ~80%',
      },
    ],
    requiresHuman: false,
    status: 'applied',
    timestamp: '2026-04-23T04:31:20Z',
    diffFile: 'dags/reporting_daily.py',
    diffOld: [
      "    slack_webhook=SlackWebhookOperator(",
      "    http_conn_id='slack_alerts',",
      "    retry_delay=timedelta(minutes=1),",
    ],
    diffNew: [
      "    slack_webhook=SlackWebhookOperator(",
      "    http_conn_id='slack_alerts',",
      "    retry_delay=timedelta(hours=1),",
      "    batch_mode=True,",
    ],
  },
];

export const AUDIT_EVENTS: AuditEvent[] = [
  { id: 'ae_001', type: 'failure_detected', description: 'Failure detected in dag=data_ingestion_v3, task=fetch_external_api', entityId: 'ep_001', timestamp: '2026-04-23T08:14:32Z', dag: 'data_ingestion_v3' },
  { id: 'ae_002', type: 'plan_generated', description: 'Repair plan generated for ep_001 (timeout, confidence=0.97)', entityId: 'plan_ep_001', timestamp: '2026-04-23T08:15:01Z', dag: 'data_ingestion_v3' },
  { id: 'ae_003', type: 'patch_applied', description: 'Auto-patch applied to data_ingestion_v3.py — timeout 30→120, retries 0→3', entityId: 'plan_ep_001', timestamp: '2026-04-23T08:15:12Z', commitHash: 'a3f8c12', dag: 'data_ingestion_v3' },
  { id: 'ae_004', type: 'failure_detected', description: 'Failure detected in dag=ml_pipeline_prod, task=load_training_data', entityId: 'ep_002', timestamp: '2026-04-23T07:55:10Z', dag: 'ml_pipeline_prod' },
  { id: 'ae_005', type: 'plan_generated', description: 'Repair plan generated for ep_002 (missing_file, confidence=0.91)', entityId: 'plan_ep_002', timestamp: '2026-04-23T07:55:45Z', dag: 'ml_pipeline_prod' },
  { id: 'ae_006', type: 'human_approved', description: 'Human approval granted for plan_ep_002 (path change required review)', entityId: 'plan_ep_002', timestamp: '2026-04-23T07:58:22Z', dag: 'ml_pipeline_prod' },
  { id: 'ae_007', type: 'patch_applied', description: 'Patch applied to ml_pipeline_prod.py — data path updated, FileSensor added', entityId: 'plan_ep_002', timestamp: '2026-04-23T07:58:35Z', commitHash: 'b7d4e91', dag: 'ml_pipeline_prod' },
  { id: 'ae_008', type: 'failure_detected', description: 'Failure detected in dag=reporting_daily, task=export_to_postgres', entityId: 'ep_003', timestamp: '2026-04-23T07:31:45Z', dag: 'reporting_daily' },
  { id: 'ae_009', type: 'plan_generated', description: 'Repair plan generated for ep_003 (missing_db, confidence=0.88)', entityId: 'plan_ep_003', timestamp: '2026-04-23T07:32:10Z', dag: 'reporting_daily' },
  { id: 'ae_010', type: 'failure_detected', description: 'Failure detected in dag=etl_transform_v2, task=normalize_schema', entityId: 'ep_004', timestamp: '2026-04-23T06:48:22Z', dag: 'etl_transform_v2' },
  { id: 'ae_011', type: 'plan_generated', description: 'Repair plan generated for ep_004 (missing_column, confidence=0.94)', entityId: 'plan_ep_004', timestamp: '2026-04-23T06:48:58Z', dag: 'etl_transform_v2' },
  { id: 'ae_012', type: 'failure_detected', description: 'Failure detected in dag=data_ingestion_v3, task=validate_response', entityId: 'ep_005', timestamp: '2026-04-23T06:21:07Z', dag: 'data_ingestion_v3' },
  { id: 'ae_013', type: 'plan_generated', description: 'Repair plan generated for ep_005 (http_error, confidence=0.99)', entityId: 'plan_ep_005', timestamp: '2026-04-23T06:21:40Z', dag: 'data_ingestion_v3' },
  { id: 'ae_014', type: 'patch_applied', description: 'Auto-patch applied to data_ingestion_v3.py — retryable status codes expanded', entityId: 'plan_ep_005', timestamp: '2026-04-23T06:21:51Z', commitHash: 'c2a9f05', dag: 'data_ingestion_v3' },
  { id: 'ae_015', type: 'rollback_executed', description: 'Rollback executed for plan_ep_007 — rejected patch reverted', entityId: 'plan_ep_007', timestamp: '2026-04-23T05:25:44Z', commitHash: 'd1e6b78', dag: 'user_activity_etl' },
  { id: 'ae_016', type: 'patch_applied', description: 'Auto-patch applied to reporting_daily.py — Slack retry delay 60s→3600s', entityId: 'plan_ep_008', timestamp: '2026-04-23T04:31:20Z', commitHash: 'e5f3a22', dag: 'reporting_daily' },
];

export const PATCH_RECORDS: PatchRecord[] = [
  { id: 'patch_001', planId: 'plan_ep_001', fileModified: 'dags/data_ingestion_v3.py', appliedAt: '2026-04-23T08:15:12Z', commitHash: 'a3f8c12', status: 'applied' },
  { id: 'patch_002', planId: 'plan_ep_002', fileModified: 'dags/ml_pipeline_prod.py', appliedAt: '2026-04-23T07:58:35Z', commitHash: 'b7d4e91', status: 'applied' },
  { id: 'patch_003', planId: 'plan_ep_005', fileModified: 'dags/data_ingestion_v3.py', appliedAt: '2026-04-23T06:21:51Z', commitHash: 'c2a9f05', status: 'applied' },
  { id: 'patch_004', planId: 'plan_ep_006', fileModified: 'dags/feature_store_sync.py', appliedAt: '2026-04-22T22:14:08Z', commitHash: 'd1e6b78', status: 'rolled_back' },
  { id: 'patch_005', planId: 'plan_ep_008', fileModified: 'dags/reporting_daily.py', appliedAt: '2026-04-23T04:31:20Z', commitHash: 'e5f3a22', status: 'applied' },
];

export const ACTIVITY_FEED = [
  { type: 'failure', icon: '🔴', text: 'Failure detected: ep_001 — data_ingestion_v3/fetch_external_api (timeout)', time: '08:14:32' },
  { type: 'plan', icon: '🟡', text: 'Repair plan generated: plan_ep_001 — confidence 97%', time: '08:15:01' },
  { type: 'applied', icon: '🟢', text: 'Patch applied: data_ingestion_v3.py — timeout 30→120s', time: '08:15:12' },
  { type: 'failure', icon: '🔴', text: 'Failure detected: ep_002 — ml_pipeline_prod/load_training_data (missing_file)', time: '07:55:10' },
  { type: 'plan', icon: '🟡', text: 'Repair plan generated: plan_ep_002 — confidence 91%', time: '07:55:45' },
  { type: 'approved', icon: '⚪', text: 'Human approved: plan_ep_002 — path change confirmed', time: '07:58:22' },
  { type: 'applied', icon: '🟢', text: 'Patch applied: ml_pipeline_prod.py — path updated + FileSensor', time: '07:58:35' },
  { type: 'failure', icon: '🔴', text: 'Failure detected: ep_003 — reporting_daily/export_to_postgres (missing_db)', time: '07:31:45' },
  { type: 'plan', icon: '🟡', text: 'Repair plan generated: plan_ep_003 — confidence 88%', time: '07:32:10' },
  { type: 'rollback', icon: '🔵', text: 'Rollback executed: plan_ep_006 — feature_store_sync.py reverted', time: '05:25:44' },
  { type: 'applied', icon: '🟢', text: 'Patch applied: reporting_daily.py — Slack rate limit handling', time: '04:31:20' },
];

export const FAILURE_CLASS_DISTRIBUTION = [
  { class: 'timeout', count: 24, color: '#f59e0b' },
  { class: 'http_error', count: 18, color: '#ef4444' },
  { class: 'missing_file', count: 10, color: '#3b82f6' },
  { class: 'missing_column', count: 6, color: '#8b5cf6' },
  { class: 'missing_db', count: 2, color: '#f97316' },
];

export const KPI_DATA = {
  totalEpisodes: 60,
  autoPatchRate: 78.3,
  mttr: '4.2 min',
  pendingReview: 2,
};

export const INTELLIGENCE_DATA = {
  testAccuracy: 0.967,
  trainAccuracy: 0.991,
  totalEpisodes: 60,
  modelFile: 'pipeline.pkl',
  classifierAgreement: { agreed: 58, total: 60 },
  confusionMatrix: [
    [23, 1, 0, 0, 0],
    [0, 17, 1, 0, 0],
    [0, 0, 10, 0, 0],
    [0, 0, 0, 5, 1],
    [0, 0, 0, 0, 2],
  ],
};
