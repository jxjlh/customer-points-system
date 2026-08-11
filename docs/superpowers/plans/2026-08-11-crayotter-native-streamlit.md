# Crayotter Native Streamlit Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken localhost iframe integration with a native Streamlit workbench that controls a private local Crayotter backend and supports runtime API replacement.

**Architecture:** Add a focused Python client/runtime module that owns backend lifecycle, API calls, uploads, safe configuration patches, and artifact reads. Keep `modules/video_editor.py` responsible only for Streamlit presentation. The browser communicates exclusively with Streamlit; Streamlit communicates with Crayotter over `127.0.0.1`.

**Tech Stack:** Python 3.13, Streamlit, Crayotter HTTP API, unittest, FFmpeg, LangGraph/OpenAI-compatible APIs

## Global Constraints

- Crayotter backend must listen only on `127.0.0.1`.
- No iframe or browser-visible localhost URL is allowed.
- Blank API Key fields preserve stored keys.
- Secrets must never be printed in UI diagnostics or logs added by this change.
- Existing Crayotter orchestration and artifact registry behavior must remain unchanged.

---

### Task 1: Backend Client Contract

**Files:**
- Create: `tests/test_crayotter_client.py`
- Create: `modules/crayotter_client.py`

**Interfaces:**
- Produces: `CrayotterClient`, `merge_profile_config`, `safe_upload_name`, `save_uploaded_files`, `artifact_path`
- Consumes: Crayotter JSON HTTP routes and `crayotter_runtime` paths

- [ ] **Step 1: Write failing tests** for URL construction, blank-key preservation, safe filenames, upload de-duplication, and artifact path boundaries.
- [ ] **Step 2: Run `python -m unittest tests.test_crayotter_client -v`** and verify failures are caused by the missing module.
- [ ] **Step 3: Implement the minimal client and pure helpers** using `urllib.request`, bounded file reads, and local runtime paths.
- [ ] **Step 4: Re-run the focused tests** and verify all client tests pass.

### Task 2: Python 3.13 Backend Startup

**Files:**
- Create: `crayotter/tests/test_backend_python313.py`
- Modify: `requirements.txt`
- Create: `crayotter/requirements-streamlit.txt`
- Create: `packages.txt`

**Interfaces:**
- Consumes: `app.backend.server.build_http_server`
- Produces: a deploy environment that imports the existing backend and provides FFmpeg

- [ ] **Step 1: Add an import/health regression test** that constructs and closes an ephemeral backend server.
- [ ] **Step 2: Run the test** and retain the observed `ModuleNotFoundError: cgi` failure as RED evidence.
- [ ] **Step 3: Add deployment dependencies** including `legacy-cgi`, Crayotter runtime libraries, and `ffmpeg` system package.
- [ ] **Step 4: Install only missing local verification dependencies if needed**, then verify backend import and `/health` behavior.

### Task 3: Native Streamlit Workbench

**Files:**
- Create: `tests/test_video_editor_module.py`
- Replace: `modules/video_editor.py`

**Interfaces:**
- Consumes: `CrayotterClient` lifecycle/config/job/upload/artifact methods
- Produces: `show_video_editor()` native Streamlit page

- [ ] **Step 1: Write a source-boundary test** asserting the module contains no iframe and exposes native task/config helpers.
- [ ] **Step 2: Run the test** and verify the iframe assertion fails against the old module.
- [ ] **Step 3: Implement native tabs** for task creation, task center, outputs/logs, API configuration, and diagnostics.
- [ ] **Step 4: Add automatic backend startup** with actionable failure messages and manual retry controls.
- [ ] **Step 5: Re-run focused tests** and compile both new modules.

### Task 4: Integration Verification

**Files:**
- Modify only files required by failed checks.

**Interfaces:**
- Consumes: completed native workbench and backend runtime
- Produces: verified deployable repository state

- [ ] **Step 1: Run focused root tests** with `python -m unittest tests.test_crayotter_client tests.test_video_editor_module -v`.
- [ ] **Step 2: Run Crayotter backend tests** with `PYTHONPATH=crayotter python -m unittest crayotter.tests.test_backend_python313 -v`.
- [ ] **Step 3: Start the backend on an ephemeral local port** and request `/health`, `/config`, and `/jobs`.
- [ ] **Step 4: Run Python compile checks** for changed modules.
- [ ] **Step 5: Review `git diff --check` and repository status**, then commit and push to `origin/main`.

