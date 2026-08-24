# TABLEAU2PBI V11.1 Connectivity Fix

This build corrects the frontend/backend compatibility check.

## Root cause
The V11 frontend still required a backend version beginning with `10.`. Therefore a healthy V11.0 backend was incorrectly reported as an old or unreachable backend.

## Correction
- The frontend now accepts TABLEAU2PBI backend major version 11 or later.
- The backend version is updated to 11.1.0.
- The health check still validates the application identity before upload.

## Run
From the application root, run `start_tableau2pbi.ps1`, or start backend and frontend in separate terminals.
