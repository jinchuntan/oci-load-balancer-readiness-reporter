# OCI Load Balancer Readiness Reporter

Standalone OCI automation tool that inventories load balancers, listeners, backend sets, and backend health, correlates backend targets to Compute instances/VNICs, and uploads JSON + Markdown reports to OCI Object Storage.

## Purpose

This tool gives operations teams a clear readiness view of OCI Load Balancer backend health and dependency mapping.

Services used:

- OCI Load Balancer
- OCI Compute
- OCI Virtual Network
- OCI Identity
- OCI Object Storage

No destructive actions are performed.

## Quick Start (Windows PowerShell)

```powershell
cd <path-to-repo>\oci-load-balancer-readiness-reporter
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Local-only run (skip Object Storage upload):

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1 -SkipUpload
```

## Manual Setup

```powershell
cd <path-to-repo>\oci-load-balancer-readiness-reporter
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run_audit.py
```

## Environment Variables

See `.env.example`.

Common values:

- `OCI_CONFIG_PROFILE`
- `OCI_REGION`
- `OCI_ROOT_COMPARTMENT_OCID`
- `OCI_INCLUDE_SUBCOMPARTMENTS`
- `OCI_OBJECT_STORAGE_NAMESPACE` (optional)
- `OCI_OBJECT_STORAGE_BUCKET` (optional; auto-discovery if omitted)
- `OCI_OBJECT_STORAGE_PREFIX`

## Output Artifacts

Local folder (default `output/`):

- `lb_readiness_report_<timestamp>.json`
- `lb_readiness_report_<timestamp>.md`

Uploaded URI pattern:

- `oci://<bucket>@<namespace>/<prefix>/lb_readiness_report_<timestamp>.json`
- `oci://<bucket>@<namespace>/<prefix>/lb_readiness_report_<timestamp>.md`

## Evidence Steps

### Terminal evidence

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Capture:

- compartment discovery count
- per-compartment LB collection logs
- generated local report paths
- uploaded `oci://...` object URIs

### Object Storage evidence

Use namespace and bucket from the printed URI:

```powershell
oci os object list `
  --namespace-name <namespace> `
  --bucket-name <bucket> `
  --prefix lb-readiness-report
```

Optional object metadata check:

```powershell
oci os object head `
  --namespace-name <namespace> `
  --bucket-name <bucket> `
  --name "lb-readiness-report/<artifact-file-name>"
```

## Safety

- Read-only API calls to Load Balancer/Compute/Networking/Identity
- Only write operation is Object Storage upload
- No create/update/delete resource actions
