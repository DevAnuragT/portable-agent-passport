#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / 'passport-fleet'
A = [
('api-docs-auditor','API Documentation Auditor','developer-tools','Find undocumented API routes and produce evidence-backed documentation actions.', [('routes','API routes','positive',1),('openapi_spec','OpenAPI specification','required',None),('examples','request examples','min_length',20)]),
('repo-health-auditor','Repository Health Auditor','developer-tools','Inspect repository metadata and identify maintainability risks.', [('readme','README','min_length',80),('tests','test suite','positive',1),('license','license','required',None)]),
('docker-readiness-auditor','Docker Readiness Auditor','developer-tools','Check whether a project is prepared for reproducible container execution.', [('dockerfile','Dockerfile','required',None),('healthcheck','health check','required',None),('base_image','base image','required',None)]),
('dependency-risk-auditor','Dependency Risk Auditor','developer-tools','Review dependency inventory for freshness, pinning, and known review gaps.', [('dependencies','dependency inventory','positive',1),('lockfile','lockfile','required',None),('review_date','review date','required',None)]),
('environment-auditor','Environment Configuration Auditor','developer-tools','Detect missing and unsafe environment configuration declarations.', [('required_variables','required variables','positive',1),('example_env','example environment','required',None),('secret_policy','secret policy','min_length',40)]),
('git-hygiene-auditor','Git Hygiene Auditor','developer-tools','Review repository hygiene, ignore rules, and contribution traceability.', [('gitignore','gitignore','required',None),('branch_policy','branch policy','min_length',40),('contributing','contribution guide','min_length',60)]),
('sql-migration-auditor','SQL Migration Auditor','developer-tools','Check database migrations for reversibility and operational safety evidence.', [('migration_files','migration files','positive',1),('rollback_plan','rollback plan','min_length',60),('backup_plan','backup plan','min_length',60)]),
('security-config-auditor','Security Configuration Auditor','cybersecurity','Review application security configuration and identify missing controls.', [('threat_model','threat model','min_length',80),('security_headers','security headers','positive',1),('incident_contact','incident contact','required',None)]),
('ci-failure-diagnostician','CI Failure Diagnostician','developer-tools','Turn CI evidence into deterministic failure categories and repair actions.', [('workflow_logs','workflow logs','min_length',20),('failed_step','failed step','required',None),('reproduction','reproduction command','min_length',20)]),
('performance-reviewer','Performance Review Agent','developer-tools','Review measured performance evidence and propose bounded optimisation work.', [('baseline_ms','baseline latency','positive',1),('sample_size','sample size','positive',10),('bottleneck','bottleneck evidence','min_length',60)]),
('pr-quality-reviewer','Pull Request Quality Reviewer','developer-tools','Check a pull request for scope, test evidence, and reviewer-ready context.', [('summary','change summary','min_length',80),('tests','test evidence','min_length',40),('risk','risk assessment','min_length',50)]),
('package-auditor','Package Configuration Auditor','developer-tools','Audit package metadata, scripts, and release readiness.', [('package_name','package name','required',None),('version','package version','required',None),('test_script','test script','required',None)]),
('log-quality-auditor','Log Quality Auditor','developer-tools','Review operational logs for structure, context, and privacy-safe diagnostics.', [('structured_events','structured events','positive',1),('correlation_id','correlation id','required',None),('redaction_policy','redaction policy','min_length',50)]),
('license-compliance-checker','License Compliance Checker','developer-tools','Check third-party dependency licensing evidence and attribution readiness.', [('inventory','license inventory','positive',1),('notices','notices file','required',None),('reviewer','review owner','required',None)]),
('cloud-deployment-auditor','Cloud Deployment Readiness Auditor','developer-tools','Review cloud deployment evidence for observability, rollback, and configuration safety.', [('deployment_target','deployment target','required',None),('rollback','rollback procedure','min_length',80),('monitoring','monitoring plan','min_length',80)]),
('accessibility-content-auditor','Accessibility Content Auditor','education','Find explainable accessibility-content gaps in a local document review.', [('document_language','document language','required',None),('page_title','page title','required',None),('alt_text_review','alternative text review','positive',1)]),
('appointment-prep-assistant','Appointment Preparation Assistant','healthcare','Turn administrative appointment details into a non-clinical preparation checklist.', [('time','appointment time','required',None),('location','location','required',None),('questions','questions','positive',1),('documents','documents','positive',1)]),
('study-workload-planner','Study Workload Planner','education','Check whether a study plan fits deadlines, available days, and daily capacity.', [('tasks','study tasks','positive',1),('available_days','available days','positive',1),('daily_capacity','daily capacity','positive',1)]),
('resume-match-advisor','Resume Match Advisor','hr-recruiting','Compare candidate evidence with role requirements while exposing missing information.', [('candidate_skills','candidate skills','positive',1),('role_requirements','role requirements','positive',1),('reviewer','human reviewer','required',None)]),
('support-triage-agent','Customer Support Triage Agent','customer-support','Classify support cases by evidence, urgency, and routing completeness.', [('customer_message','customer message','min_length',20),('product_area','product area','required',None),('urgency_signal','urgency signal','required',None)]),
('inventory-restock-advisor','Inventory Restock Advisor','retail','Identify restock candidates from stock, demand, and lead-time evidence.', [('stock_level','stock level','positive',0),('demand_rate','demand rate','positive',0),('lead_time_days','lead time','positive',1)]),
('travel-constraint-checker','Travel Constraint Checker','travel','Check an itinerary against dates, budget, accessibility, and document constraints.', [('itinerary','itinerary','positive',1),('budget','budget','positive',1),('travel_documents','travel documents','positive',1)]),
('product-comparison-advisor','Product Comparison Advisor','retail','Compare products using explicit criteria and identify trade-offs rather than inventing a winner.', [('products','products','positive',2),('criteria','comparison criteria','positive',2),('budget','budget','positive',1)]),
('budget-auditor','Personal Budget Auditor','finance','Check a personal budget for missing categories, arithmetic evidence, and review boundaries.', [('income','income','positive',1),('expenses','expense categories','positive',1),('savings_goal','savings goal','positive',0)]),
('invoice-consistency-checker','Invoice Consistency Checker','finance','Detect missing invoice fields and inconsistent totals without making payment decisions.', [('invoice_number','invoice number','required',None),('line_items','line items','positive',1),('total','invoice total','positive',0)]),
('contract-clause-checker','Contract Clause Checklist Agent','legal','Check a contract draft for explicitly requested clauses and human-review flags.', [('contract_text','contract text','min_length',200),('required_clauses','required clauses','positive',1),('legal_reviewer','legal reviewer','required',None)]),
('content-quality-auditor','Content Quality Auditor','marketing-sales','Review content for audience, evidence, clarity, and accessibility signals.', [('content','content','min_length',120),('audience','audience','required',None),('call_to_action','call to action','required',None)]),
('interview-plan-builder','Interview Plan Builder','hr-recruiting','Build a structured interview plan from competencies, role level, and evaluation evidence.', [('competencies','competencies','positive',1),('role_level','role level','required',None),('rubric','evaluation rubric','min_length',80)]),
('property-match-advisor','Property Match Advisor','real-estate','Compare property listings against buyer constraints and expose compromises.', [('listings','property listings','positive',1),('must_haves','must-have criteria','positive',1),('budget','budget','positive',1)]),
('maintenance-checker','Maintenance Checklist Agent','manufacturing','Check maintenance work orders for asset, safety, parts, and sign-off completeness.', [('asset_id','asset id','required',None),('safety_isolation','safety isolation','required',None),('parts','parts list','positive',1),('signoff','sign-off','required',None)]),
('supply-delay-analyzer','Supply Delay Analyzer','supply-chain','Identify supply-chain delay evidence and produce traceable mitigation actions.', [('shipment_id','shipment id','required',None),('expected_date','expected date','required',None),('delay_reason','delay reason','min_length',20)]),
('citation-checker','Research Citation Checker','research','Check research notes for source identity, claim linkage, and citation completeness.', [('claims','claims','positive',1),('sources','sources','positive',1),('citation_map','citation map','positive',1)]),
('incident-checklist-agent','Cybersecurity Incident Checklist Agent','cybersecurity','Check incident records for containment, evidence preservation, and escalation completeness.', [('incident_id','incident id','required',None),('containment','containment action','min_length',60),('evidence_preservation','evidence preservation','required',None),('escalation_owner','escalation owner','required',None)]),
('data-quality-profiler','Data Quality Profiler','data-analytics','Profile a dataset declaration for schema, freshness, null handling, and ownership evidence.', [('schema','schema','positive',1),('row_count','row count','positive',1),('freshness','freshness timestamp','required',None),('owner','data owner','required',None)]),
('discharge-auditor','Discharge Instruction Auditor','healthcare','Check discharge instructions for completeness, readability, and safety escalation guidance.', [('patient_instructions','patient instructions','min_length',120),('warning_signs','warning signs','positive',1),('follow_up','follow-up plan','required',None),('clinician_review','clinician review','required',None)]),
]

def W(p,s): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s.rstrip()+'\n',encoding='utf-8')
def generate(row):
    slug,title,cat,desc,rules=row; root=ROOT/slug
    if root.exists(): shutil.rmtree(root)
    skill=f'{slug}-skill'; tool=f'audit-{slug}'
    W(root/'agent.yaml', f'''spec_version: "0.1.0"
name: {slug}
version: 0.1.0
description: {desc}
skills:
  - {skill}
tools:
  - {tool}
tags:
  - {cat}
  - evidence-driven''')
    W(root/'SOUL.md', f'''# Identity

I am {title}, a focused evidence-driven agent for {cat}. I inspect declared inputs, apply transparent deterministic checks, and produce findings that a human can review.

## Core Identity

My purpose is to {desc.lower()}

## Communication Style

I report status, evidence, and recommended action separately. I do not hide missing data or convert a review aid into professional certification.

## Values & Principles

I value observable evidence, reproducibility, privacy-safe processing, and human ownership of consequential decisions.

## Domain Expertise

I specialise in {cat} workflows represented by the fields in my input contract.''')
    W(root/'RULES.md', '''# Rules

## Must Always

- Check every declared field and cite the field as evidence.
- Return explicit findings and remediation actions.
- Preserve caller data locally and avoid network access.
- Escalate consequential decisions to a human reviewer.

## Must Never

- Invent evidence, credentials, or external verification.
- Claim regulatory, clinical, legal, financial, or security certification.
- Treat missing input as a passing result.

## Output Constraints

Return JSON-serialisable output with status, score, domain, findings, and checked rules.

## Safety and Ethics

This is a decision-support audit, not a substitute for a qualified professional or an official compliance process.''')
    W(root/'DUTIES.md', '''# Maker

The Maker defines domain checks and prepares evidence-backed findings.

# Checker

The Checker reviews findings, checks that evidence is present, and rejects unsupported claims.''')
    W(root/'AGENTS.md', f'''# Agent instructions

Run the {title} using the documented JSON input contract. Prefer deterministic checks, explain every finding, and state limitations clearly.''')
    W(root/'EXPLAINABILITY.md', f'''# Decision and Reasoning

The agent first checks that the input is an object and then evaluates each {title} rule independently. A finding is produced when evidence is missing or fails the rule, so the final status is derived from observed fields rather than an opaque score.

# Inputs and Data Sources

Inputs are caller-provided JSON fields for the {cat} workflow. The data sources used are only the supplied payload and the repository's checked-in rule definitions; the agent does not browse the web or call a remote model.

# Known Limitations and Constraints

The agent is a deterministic pre-review aid and cannot establish that a real-world process is safe, compliant, clinically correct, or complete. Human review remains required, and the result is limited by the evidence present in the input payload.''')
    W(root/'README.md', f'''# {title}

{desc}

## Evidence-driven architecture

```text
JSON input → domain rules → finding collector → status + score + remediation
                                      ↓
                         native / OpenAI / CrewAI / Claude / Lyzr adapters
```

The core is deterministic and framework-neutral. Each finding contains the rule, severity, observed evidence, and suggested action. This agent does not claim certification or official platform points.

## Run

```bash
python3 agent.py examples/good-input.json
python3 -m unittest discover -s tests -v
python3 tools/{tool}.py examples/good-input.json
```

## Scope and limitations

This is a focused {cat} review aid. It uses no network calls, credentials, or paid APIs. A human must review the result before acting on it.''')
    rc='\n'.join(f'    ({f!r}, {l!r}, {k!r}, {t!r}),' for f,l,k,t in rules)
    W(root/'agent.py', f'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
from typing import Any
DOMAIN = {title!r}
RULES = [
{rc}
]
def audit(payload: dict[str, Any]) -> dict[str, Any]:
    findings=[]; passed=0
    for field,label,kind,threshold in RULES:
        value=payload.get(field); missing=value is None or value=='' or value==[] or value=={{}}; ok=not missing
        if ok and kind=='positive':
            ok=(len(value)>=threshold if isinstance(value,(list,tuple,dict)) else isinstance(value,(int,float)) and value>=threshold)
        elif ok and kind=='min_length': ok=isinstance(value,str) and len(value.strip())>=threshold
        if ok: passed+=1
        else: findings.append({{'rule':field,'severity':'error','message':f'Missing or insufficient {{label}} evidence','evidence':repr(value),'fix':f'Provide {{label}} evidence satisfying the {{kind}} rule.'}})
    return {{'domain':DOMAIN,'status':'pass' if passed==len(RULES) else 'needs-review','score':{{'passed':passed,'total':len(RULES)}},'findings':findings,'checked_rules':[r[0] for r in RULES]}}
if __name__=='__main__':
    source=Path(sys.argv[1]) if len(sys.argv)>1 else None
    payload=json.loads(source.read_text() if source else sys.stdin.read())
    print(json.dumps(audit(payload),indent=2,sort_keys=True))''')
    good={f:(['evidence']*max(t or 1,1) if k=='positive' else ('evidence '*((t or 20)//9+1) if k=='min_length' else 'provided')) for f,l,k,t in rules}
    W(root/'examples/good-input.json', json.dumps(good,indent=2)); W(root/'examples/bad-input.json', json.dumps({rules[0][0]:''},indent=2))
    W(root/f'skills/{skill}/SKILL.md', f'''---
name: {skill}
description: Apply transparent {cat} evidence checks and explain remediation.
---

# {title} skill

Inspect declared JSON fields, apply each domain rule, report evidence, and keep unresolved findings visible to a human reviewer.''')
    W(root/f'tools/{tool}.yaml', f'''name: {tool}
description: Run the {title} evidence audit
version: 0.1.0
input_schema:
  type: object
  properties:
    payload: {{type: object, description: Domain-specific evidence payload}}
  required: [payload]
output_schema:
  type: object
  properties:
    status: {{type: string}}
    score: {{type: object}}
    findings: {{type: array}}
implementation:
  type: script
  path: {tool}.py
  runtime: python3''')
    W(root/f'tools/{tool}.py', f'''import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent import audit
payload=json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv)>1 else json.load(sys.stdin)
print(json.dumps(audit(payload),indent=2,sort_keys=True))''')
    W(root/'adapters/base.py','from agent import audit\ndef run(payload): return audit(payload)')
    for a in ('openai','crewai','claude','lyzr'): W(root/f'adapters/{a}_adapter.py','from .base import run\ndef execute(payload): return run(payload)')
    W(root/'tests/test_agent.py', '''import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from agent import audit,RULES
class AgentTests(unittest.TestCase):
 def test_good_fixture_passes(self):
  r=audit(json.loads((Path(__file__).parents[1]/'examples/good-input.json').read_text())); self.assertEqual(r['status'],'pass'); self.assertEqual(r['score']['passed'],len(RULES))
 def test_missing_evidence_needs_review(self):
  r=audit({}); self.assertEqual(r['status'],'needs-review'); self.assertEqual(len(r['findings']),len(RULES))
if __name__=='__main__': unittest.main()''')
    W(root/'.gitignore','__pycache__/\n*.pyc\n.venv/')

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    for row in A: generate(row)
    W(ROOT/'FLEET_INDEX.json',json.dumps([{'slug':x[0],'title':x[1],'category':x[2]} for x in A],indent=2))
    print(f'generated {len(A)} agents in {ROOT}')
if __name__=='__main__': main()
