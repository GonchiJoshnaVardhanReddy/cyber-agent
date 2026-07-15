# Rules of Engagement (active — replace with your real engagement details)
# This is a SAMPLE file. The agent will accept it but you MUST fill in real values.
# IMPORTANT: Update these values for YOUR actual engagement!

Engagement ID: ENG-2026-DEMO  # Change this to your actual engagement ID
Engagement Type: Security Research (local lab only)
Client / Program Name: Local Test Lab
Program URL: N/A (private lab)
Engagement Start: 2026-01-01 00:00 (UTC)
Engagement End: 2026-12-31 23:59 (UTC)
Lead Operator: operator
Authorization Reference: Local lab, owned by operator

Authorized Scope:
  In-Scope Targets:
    - scanme.nmap.org  # Replace with YOUR authorized targets
    - 127.0.0.1        # Only if testing on your own localhost
    - localhost        # Only if testing on your own localhost
  Out-of-Scope:
    - everything else

Allowed Activity Types:
  - Passive reconnaissance
  - Active reconnaissance
  - Web application testing
  - API security testing

Prohibited Actions:
  - Network exploitation
  - Privilege escalation against non-owned systems
  - DoS/DDoS
  - Modifying production data

Signed: operator
Date: 2026-01-01
