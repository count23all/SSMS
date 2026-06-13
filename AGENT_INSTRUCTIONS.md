  ## Agent Communications

  You work in parallel with the other agents. Coordinate through the local message bus in `ssms/` (Stupidly Simple Messaging Service). Use your assigned name as your identity everywhere.

  - **Start every turn by checking your mail:**
    `python ssms/get.py "<you>"`
    Prints only your unread messages (newest first) and marks them read. Respond if needed.

  - **Send a message:**
    `python ssms/put.py "<you>" --to "Claude B" "Codex" --msg "your message"`
    First name is you (sender); `--to` lists recipients; `--to all` broadcasts.

  - **Look back without consuming:** `python ssms/history.py "<you>"`
    (or `python ssms/history.py --id <id>` to see a thread + who's read it).

  Don't hand-edit message files — `get`/`put`  handle read-tracking and delivery for you.
  
* Every turn always check for new message from the other agents and respond if necessary or generate your own if required.
