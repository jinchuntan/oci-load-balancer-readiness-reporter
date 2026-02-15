# ACE Contribution Sample

## Title
OCI Load Balancer Readiness Reporter with Backend-to-Instance Correlation

## Description
This OCI Python SDK automation discovers load balancers across compartments, evaluates backend-set and backend health, and maps backend IP targets to Compute instances via VNIC metadata. It outputs JSON and Markdown readiness reports and uploads them to OCI Object Storage for operational evidence. The workflow is non-destructive and uses read-only OCI APIs except Object Storage uploads.

## Suggested Product Tags
- Oracle Cloud Infrastructure
- OCI Python SDK
- Load Balancer
- Compute
- Virtual Cloud Network (VCN)
- Object Storage
- Operations
- Automation
- Reliability
