"""Industry frameworks the swarm is aligned to, with the controls it covers.

Control IDs are limited to ones the agents' skills actually exercise; coverage is
computed from which agents/skills reference each framework.
"""

STANDARDS = [
    {"id": "nist-csf-2", "name": "NIST CSF 2.0", "publisher": "NIST",
     "url": "https://www.nist.gov/cyberframework",
     "description": "Cybersecurity Framework 2.0: Govern, Identify, Protect, Detect, Respond, Recover.",
     "controls": [
         ("DE.CM", "Continuous monitoring of assets and networks"),
         ("DE.AE", "Adverse event analysis"),
         ("RS.MA", "Incident management"),
         ("RS.AN", "Incident analysis"),
         ("RS.MI", "Incident mitigation"),
         ("RS.CO", "Incident response reporting and communication"),
         ("ID.RA", "Risk assessment"),
         ("GV.OV", "Oversight of cybersecurity risk strategy"),
     ]},
    {"id": "nist-800-61r3", "name": "NIST SP 800-61r3", "publisher": "NIST",
     "url": "https://csrc.nist.gov/pubs/sp/800/61/r3/final",
     "description": "Incident Response Recommendations and Considerations for Cybersecurity Risk Management (CSF 2.0 aligned).",
     "controls": [
         ("Detect", "Detection and analysis of adverse events"),
         ("Respond", "Containment, eradication and incident handling"),
         ("Recover", "Restoration and lessons learned"),
         ("Govern", "IR roles, policies and continuous improvement"),
     ]},
    {"id": "nist-800-53r5", "name": "NIST SP 800-53 Rev. 5", "publisher": "NIST",
     "url": "https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final",
     "description": "Security and privacy controls for information systems.",
     "controls": [
         ("IR-4", "Incident handling"), ("IR-5", "Incident monitoring"), ("IR-6", "Incident reporting"),
         ("SI-4", "System monitoring"), ("RA-5", "Vulnerability monitoring and scanning"),
         ("AU-6", "Audit record review, analysis and reporting"), ("CA-7", "Continuous monitoring"),
     ]},
    {"id": "mitre-attack", "name": "MITRE ATT&CK v17", "publisher": "MITRE",
     "url": "https://attack.mitre.org",
     "description": "Adversary tactics and techniques knowledge base used for mapping detections and hunts.",
     "controls": [
         ("TA0001", "Initial Access"), ("TA0002", "Execution"), ("TA0003", "Persistence"),
         ("TA0004", "Privilege Escalation"), ("TA0005", "Defense Evasion"), ("TA0006", "Credential Access"),
         ("TA0007", "Discovery"), ("TA0008", "Lateral Movement"), ("TA0011", "Command and Control"),
         ("TA0040", "Impact"),
     ]},
    {"id": "mitre-d3fend", "name": "MITRE D3FEND", "publisher": "MITRE",
     "url": "https://d3fend.mitre.org",
     "description": "Defensive countermeasure knowledge graph; every response action maps to a D3FEND technique.",
     "controls": [
         ("D3-ITF", "Inbound Traffic Filtering"), ("D3-NI", "Network Isolation"),
         ("D3-PT", "Process Termination"), ("D3-AL", "Account Locking"), ("D3-FEV", "File Eviction"),
     ]},
    {"id": "cis-v8-1", "name": "CIS Controls v8.1", "publisher": "Center for Internet Security",
     "url": "https://www.cisecurity.org/controls",
     "description": "Prioritized safeguards for cyber defense.",
     "controls": [
         ("CIS 7", "Continuous Vulnerability Management"), ("CIS 8", "Audit Log Management"),
         ("CIS 13", "Network Monitoring and Defense"), ("CIS 17", "Incident Response Management"),
     ]},
    {"id": "iso-27001-2022", "name": "ISO/IEC 27001:2022", "publisher": "ISO/IEC",
     "url": "https://www.iso.org/standard/27001",
     "description": "Information security management systems; Annex A organizational and technological controls.",
     "controls": [
         ("A.5.24", "Information security incident management planning and preparation"),
         ("A.5.25", "Assessment and decision on information security events"),
         ("A.5.26", "Response to information security incidents"),
         ("A.5.27", "Learning from information security incidents"),
         ("A.5.28", "Collection of evidence"),
         ("A.8.8", "Management of technical vulnerabilities"),
         ("A.8.16", "Monitoring activities"),
     ]},
    {"id": "pci-dss-4", "name": "PCI DSS v4.0.1", "publisher": "PCI SSC",
     "url": "https://www.pcisecuritystandards.org",
     "description": "Payment card data security requirements.",
     "controls": [
         ("Req 6", "Develop and maintain secure systems and software"),
         ("Req 10", "Log and monitor all access to system components and cardholder data"),
         ("Req 11", "Test security of systems and networks regularly"),
         ("Req 12.10", "Incident response plan"),
     ]},
    {"id": "sans-picerl", "name": "SANS PICERL", "publisher": "SANS Institute",
     "url": "https://www.sans.org",
     "description": "Incident handling lifecycle: Preparation, Identification, Containment, Eradication, Recovery, Lessons learned.",
     "controls": [
         ("Identification", "Identify and scope the incident"), ("Containment", "Limit damage"),
         ("Eradication", "Remove the threat"), ("Recovery", "Restore operations"),
         ("Lessons Learned", "Post-incident review"),
     ]},
    {"id": "cisa-kev", "name": "CISA KEV", "publisher": "CISA",
     "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
     "description": "Known Exploited Vulnerabilities catalog; top priority for remediation.",
     "controls": [("KEV", "Known exploited vulnerability prioritization")]},
    {"id": "first-epss", "name": "FIRST EPSS", "publisher": "FIRST",
     "url": "https://www.first.org/epss",
     "description": "Exploit Prediction Scoring System: probability of exploitation in the next 30 days.",
     "controls": [("EPSS", "Exploit probability prioritization")]},
    {"id": "cisa-ssvc", "name": "CISA SSVC", "publisher": "CISA",
     "url": "https://www.cisa.gov/ssvc",
     "description": "Stakeholder-Specific Vulnerability Categorization decision tree (Track, Track*, Attend, Act).",
     "controls": [("SSVC", "Vulnerability decision categorization")]},
    {"id": "sigma", "name": "Sigma", "publisher": "SigmaHQ",
     "url": "https://sigmahq.io",
     "description": "Generic signature format for SIEM detections; used for Detection-as-Code proposals.",
     "controls": [("Sigma", "Portable detection rules")]},
    {"id": "owasp-llm-top10", "name": "OWASP Top 10 for LLM Applications", "publisher": "OWASP",
     "url": "https://genai.owasp.org",
     "description": "Agent safety: prompt injection, excessive agency and insecure output handling controls.",
     "controls": [
         ("LLM01", "Prompt Injection"), ("LLM02", "Sensitive Information Disclosure"),
         ("LLM05", "Improper Output Handling"), ("LLM06", "Excessive Agency"),
     ]},
]

STANDARDS_BY_ID = {s["id"]: s for s in STANDARDS}


def standard_ref(std_id: str) -> dict:
    s = STANDARDS_BY_ID.get(std_id)
    return {"id": std_id, "name": s["name"] if s else std_id}
