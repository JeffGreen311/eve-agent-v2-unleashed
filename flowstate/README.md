# FlowState — Visual Workflow Orchestrator

A dark-themed, PyQt6-based visual workflow builder. Drag nodes onto the canvas, connect ports, hit **Generate + Run** — FlowState writes and executes the Python for you.

> Part of the [Eve Agent V2 Unleashed](https://github.com/JeffGreen311/eve-agent-v2-unleashed) project.

---

## Features

- **Dark cyberpunk canvas** — dot-grid background, bezier connections, per-type color coding
- **Node palette** — pre-built triggers, actions, logic nodes, and outputs
- **LLM code generation** — uses Ollama to translate visual graphs into runnable Python
- **Built-in implementations** — File Trigger, Excel Reader, File Output, Condition, Email Sender, and Google Drive Uploader all run without LLM calls
- **Auto-generated tests** — one click generates and runs a full pytest suite against your workflow
- **Properties panel** — click any node to configure its settings live
- **Save / Load** — workflows saved as `.json`, generated code saved as `.py`

---

## Installation

```bash
git clone https://github.com/JeffGreen311/eve-agent-v2-unleashed.git
cd eve-agent-v2-unleashed/flowstate
pip install -r requirements.txt
```

**Run:**
```bash
python -m flowstate.app
# or from inside the flowstate/ directory:
python flowstate/app.py
```

### Requirements

| Package | Purpose |
|---------|---------|
| `PyQt6` | GUI framework |
| `openpyxl` | Excel file reading |
| `ollama` | LLM code generation |
| `pytest` | Auto-generated test runner |
| `requests` | HTTP utilities |

**Optional — only needed for specific nodes:**
| Package | Node |
|---------|------|
| `google-api-python-client` | Google Drive Uploader |
| `google-auth-oauthlib` | Google Drive Uploader |

---

## Quick Start

1. Launch FlowState
2. Click a node in the **NODE PALETTE** (left panel) to add it to the canvas
3. Drag from an **output port** (right side of a node, green) to an **input port** (left side, blue) to connect nodes
4. Select a node and configure it in the **PROPERTIES** panel (right)
5. Press **Ctrl+G** to generate Python code
6. Press **F5** to run the workflow
7. Check the **Output** tab at the bottom for results

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+G` | Generate code |
| `F5` | Run workflow |
| `Ctrl+T` / `F6` | Generate + run tests |
| `Ctrl+S` | Save workflow |
| `Ctrl+Shift+S` | Save As |
| `Ctrl+O` | Open workflow |
| `Ctrl+N` | New workflow |
| `Delete` / `Backspace` | Delete selected node or connection |
| `Ctrl+=` / `Ctrl+-` | Zoom in / out |
| `Ctrl+0` | Reset zoom |
| Mouse wheel | Zoom |

---

## Node Reference

### File Trigger
**Type:** Trigger

Provides a file path to downstream nodes. Configure in Properties:

| Property | Description | Example |
|----------|-------------|---------|
| `Path` | Full path to the file | `C:\data\report.xlsx` |
| `Event` | Event type label (informational) | `modified` |

> No file-watching is performed at runtime — this node simply passes the configured path downstream.

---

### Excel Reader
**Type:** Action  
**Input:** `file_path` (string)  
**Output:** `data` (list of dicts)

Reads every row from an `.xlsx` or `.csv` file into a list of dictionaries. Each key is a column header.

| Property | Description | Default |
|----------|-------------|---------|
| `Sheet Name` | Worksheet name to read | `Sheet1` |

**Supported formats:**
- `.xlsx` — read via `openpyxl`
- `.csv` — read via Python's built-in `csv.DictReader`
- Files saved as `.xlsx` that are actually CSV are detected and handled automatically

**Example path formats:**
```
C:\Users\you\data\sales.xlsx
C:\Users\you\data\contacts.csv
```

> Tip: Use **File Trigger → Excel Reader** to pipe a dynamic path, or set the `Path` property on File Trigger and leave the Excel Reader input connected.

---

### Email Sender
**Type:** Action  
**Inputs:** `recipient`, `subject`, `body`  
**Output:** `status` (boolean)

Sends an email via SMTP. Credentials are read from environment variables — never stored in the workflow file.

| Property | Description | Default |
|----------|-------------|---------|
| `Smtp Server` | SMTP host | `smtp.gmail.com` |
| `Port` | SMTP port | `587` |

**Required environment variables:**
```bash
set EMAIL_USER=you@gmail.com
set EMAIL_PASS=your_app_password
```

**Gmail setup (App Password required):**
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification**
3. Search for **App passwords** → create one for "Mail"
4. Use the generated 16-character password as `EMAIL_PASS`

> Your regular Gmail password will not work. Gmail requires an App Password when sending via SMTP with 2FA enabled.

**Other providers:**
| Provider | SMTP Server | Port |
|----------|-------------|------|
| Gmail | `smtp.gmail.com` | `587` |
| Outlook | `smtp.office365.com` | `587` |
| Yahoo | `smtp.mail.yahoo.com` | `587` |

---

### Google Drive Uploader
**Type:** Action  
**Input:** `file_path` (string)  
**Output:** `file_id` (string)

Uploads a local file to Google Drive using a **service account**.

| Property | Description | Default |
|----------|-------------|---------|
| `Folder Id` | Google Drive folder ID to upload into | *(root)* |

**Required environment variable:**
```bash
set GOOGLE_CREDS_JSON=C:\path\to\service-account.json
```

**Required packages:**
```bash
pip install google-api-python-client google-auth-oauthlib
```

**Service account setup:**
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or select an existing one)
3. Enable the **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create service account
5. Create a JSON key and download it
6. Set `GOOGLE_CREDS_JSON` to the path of that JSON file
7. Share your target Drive folder with the service account's email address

**Finding a folder ID:**  
Open the folder in Google Drive — the ID is the last segment of the URL:  
`https://drive.google.com/drive/folders/`**`1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs`**

---

### Condition
**Type:** Logic  
**Inputs:** `value1`, `value2` (optional)  
**Outputs:** `true`, `false`

Evaluates a comparison between two values. Use the output ports to branch your workflow.

| Property | Description | Example |
|----------|-------------|---------|
| `Operator` | Comparison operator | `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not in` |
| `Value` | Right-hand side (used if `value2` input is not connected) | `100` |

---

### File Output
**Type:** Output  
**Inputs:** `data`, `file_path` (optional)

Writes workflow data to a file. If `file_path` input is not connected, uses the `Path` property.

| Property | Description | Default |
|----------|-------------|---------|
| `Path` | Output file path | `output.json` |
| `Format` | `json` or `txt` | `json` |

---

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | Code generator | Ollama model for LLM generation. Default: `qwen3-coder:480b-cloud` |
| `EMAIL_USER` | Email Sender | SMTP sender address |
| `EMAIL_PASS` | Email Sender | SMTP password / App Password |
| `GOOGLE_CREDS_JSON` | Google Drive Uploader | Path to service account JSON key |

---

## Example Workflow: CSV → Email Report

1. **File Trigger** — set `Path` to your CSV file
2. **Excel Reader** — connect File Trigger's `file_path` output → Excel Reader's `file_path` input
3. **Email Sender** — connect outputs, fill in `recipient`, `subject`, `body` via Properties
4. Press **Ctrl+G** → **F5**

---

## License

MIT — see [LICENSE](LICENSE)
