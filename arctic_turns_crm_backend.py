# ============================================================
# Arctic Turns CRM - Frappe/ERPNext Backend Customization
# ============================================================
# File structure:
#   arctic_turns_crm/
#   ├── hooks.py
#   ├── setup.py
#   ├── custom/
#   │   ├── lead.py
#   │   ├── opportunity.py
#   │   └── crm_activity.py
#   └── fixtures/
#       ├── custom_fields.json
#       └── property_setters.json
# ============================================================


# ────────────────────────────────────────────────────────────
# hooks.py  — App entry point
# ────────────────────────────────────────────────────────────
"""
app_name = "arctic_turns_crm"
app_title = "Arctic Turns CRM"
app_publisher = "Arctic Turns"
app_description = "Internal CRM for Arctic Turns software services"
app_version = "1.0.0"

# Auto-load fixtures when the app is installed
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Arctic Turns CRM"]]
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "=", "Arctic Turns CRM"]]
    },
    "CRM Stage",
    "CRM Lead Source",
]

# DocType Event Hooks
doc_events = {
    "CRM Lead": {
        "before_save": "arctic_turns_crm.custom.lead.before_save",
        "after_insert": "arctic_turns_crm.custom.lead.after_insert",
        "on_update": "arctic_turns_crm.custom.lead.on_update",
    },
    "CRM Deal": {
        "on_update": "arctic_turns_crm.custom.opportunity.on_update",
        "before_save": "arctic_turns_crm.custom.opportunity.before_save",
    },
}

# Scheduled jobs
scheduler_events = {
    "daily": [
        "arctic_turns_crm.tasks.send_followup_reminders",
        "arctic_turns_crm.tasks.update_deal_scores",
    ],
    "weekly": [
        "arctic_turns_crm.tasks.generate_weekly_pipeline_report",
    ],
}
"""


# ────────────────────────────────────────────────────────────
# custom/lead.py  — Lead DocType customization
# ────────────────────────────────────────────────────────────

import frappe
from frappe.utils import today, add_days, nowdate
from frappe import _


# ── Custom Fields to add to CRM Lead ──────────────────────
LEAD_CUSTOM_FIELDS = [
    # Company info
    {
        "fieldname": "at_company_size",
        "label": "Company Size",
        "fieldtype": "Select",
        "options": "\n1-10\n11-50\n51-200\n201-500\n500+",
        "insert_after": "company",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_industry",
        "label": "Industry",
        "fieldtype": "Select",
        "options": "\nTechnology\nFinance\nManufacturing\nHealthcare\nRetail\nLogistics\nEducation\nOther",
        "insert_after": "at_company_size",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_annual_revenue",
        "label": "Est. Annual Revenue (₹)",
        "fieldtype": "Currency",
        "insert_after": "at_industry",
        "module": "Arctic Turns CRM",
    },
    # Services interest
    {
        "fieldname": "at_services_section",
        "label": "Services of Interest",
        "fieldtype": "Section Break",
        "insert_after": "at_annual_revenue",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_services_interested",
        "label": "Services Interested In",
        "fieldtype": "MultiCheck",
        "options": "IT Consulting\nCloud Migration\nSoftware Audit\nDigital Transformation\nManaged Services\nCustom Development\nSupport & Maintenance",
        "insert_after": "at_services_section",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_current_tech_stack",
        "label": "Current Tech Stack / ERP",
        "fieldtype": "Small Text",
        "insert_after": "at_services_interested",
        "module": "Arctic Turns CRM",
    },
    # Lead scoring
    {
        "fieldname": "at_score_section",
        "label": "Lead Scoring",
        "fieldtype": "Section Break",
        "insert_after": "at_current_tech_stack",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_lead_score",
        "label": "Lead Score (0-100)",
        "fieldtype": "Int",
        "insert_after": "at_score_section",
        "default": 50,
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_qualification_notes",
        "label": "Qualification Notes",
        "fieldtype": "Text Editor",
        "insert_after": "at_lead_score",
        "module": "Arctic Turns CRM",
    },
    # Follow-up
    {
        "fieldname": "at_followup_section",
        "label": "Follow-up",
        "fieldtype": "Section Break",
        "insert_after": "at_qualification_notes",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_next_followup_date",
        "label": "Next Follow-up Date",
        "fieldtype": "Date",
        "insert_after": "at_followup_section",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_followup_notes",
        "label": "Follow-up Notes",
        "fieldtype": "Small Text",
        "insert_after": "at_next_followup_date",
        "module": "Arctic Turns CRM",
    },
]


def before_save(doc, method=None):
    """Auto-calculate lead score based on available data."""
    score = 0

    if doc.email_id:
        score += 10
    if doc.phone:
        score += 10
    if doc.company:
        score += 15
    if doc.get("at_company_size") in ["201-500", "500+"]:
        score += 20
    elif doc.get("at_company_size") in ["51-200"]:
        score += 10
    if doc.get("at_annual_revenue") and doc.at_annual_revenue > 5000000:
        score += 20
    if doc.get("at_services_interested"):
        score += 15
    if doc.source in ["Referral", "LinkedIn"]:
        score += 10

    doc.at_lead_score = min(score, 100)

    # Auto-set next follow-up to 3 days if not set
    if not doc.get("at_next_followup_date"):
        doc.at_next_followup_date = add_days(today(), 3)


def after_insert(doc, method=None):
    """Send notification to assigned sales rep after lead is created."""
    if doc.lead_owner:
        frappe.sendmail(
            recipients=[frappe.db.get_value("User", doc.lead_owner, "email")],
            subject=f"New Lead Assigned: {doc.lead_name}",
            message=f"""
            <p>Hi,</p>
            <p>A new lead has been assigned to you:</p>
            <ul>
                <li><b>Name:</b> {doc.lead_name}</li>
                <li><b>Company:</b> {doc.company}</li>
                <li><b>Source:</b> {doc.source}</li>
                <li><b>Score:</b> {doc.get('at_lead_score', 50)}/100</li>
            </ul>
            <p>Please log in to the CRM to take action.</p>
            """,
            now=True,
        )


def on_update(doc, method=None):
    """Create follow-up task automatically when lead is marked Qualified."""
    if doc.status == "Qualified" and doc.has_value_changed("status"):
        _create_followup_task(doc)


def _create_followup_task(lead):
    task = frappe.get_doc({
        "doctype": "CRM Task",
        "title": f"Follow up with {lead.lead_name} at {lead.company}",
        "assigned_to": lead.lead_owner,
        "due_date": add_days(today(), 2),
        "priority": "High",
        "description": f"Lead qualified. Score: {lead.get('at_lead_score')}. Next step: Schedule discovery call.",
        "reference_doctype": "CRM Lead",
        "reference_docname": lead.name,
    })
    task.insert(ignore_permissions=True)
    frappe.msgprint(f"Follow-up task created for {lead.lead_name}", alert=True)


# ────────────────────────────────────────────────────────────
# custom/opportunity.py  — Deal / Opportunity customization
# ────────────────────────────────────────────────────────────

DEAL_CUSTOM_FIELDS = [
    {
        "fieldname": "at_deal_section",
        "label": "Arctic Turns Deal Info",
        "fieldtype": "Section Break",
        "insert_after": "probability",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_service_type",
        "label": "Service Type",
        "fieldtype": "Select",
        "options": "\nIT Consulting\nCloud Migration\nSoftware Audit\nDigital Transformation\nManaged Services\nCustom Development\nSupport Contract",
        "insert_after": "at_deal_section",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_implementation_timeline",
        "label": "Est. Implementation Timeline (months)",
        "fieldtype": "Int",
        "insert_after": "at_service_type",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_budget_confirmed",
        "label": "Budget Confirmed?",
        "fieldtype": "Check",
        "insert_after": "at_implementation_timeline",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_decision_maker",
        "label": "Decision Maker",
        "fieldtype": "Data",
        "insert_after": "at_budget_confirmed",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_competitors",
        "label": "Competitors in Consideration",
        "fieldtype": "Small Text",
        "insert_after": "at_decision_maker",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_why_us",
        "label": "Why Arctic Turns? (Value Prop Notes)",
        "fieldtype": "Text Editor",
        "insert_after": "at_competitors",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_proposal_sent",
        "label": "Proposal Sent?",
        "fieldtype": "Check",
        "insert_after": "at_why_us",
        "module": "Arctic Turns CRM",
    },
    {
        "fieldname": "at_proposal_date",
        "label": "Proposal Date",
        "fieldtype": "Date",
        "insert_after": "at_proposal_sent",
        "depends_on": "eval: doc.at_proposal_sent == 1",
        "module": "Arctic Turns CRM",
    },
]


def on_update(doc, method=None):
    """Auto-update probability based on stage."""
    stage_probability_map = {
        "Discovery": 20,
        "Demo": 35,
        "Proposal": 55,
        "Negotiation": 75,
        "Closed Won": 100,
        "Closed Lost": 0,
    }
    if doc.stage in stage_probability_map:
        new_prob = stage_probability_map[doc.stage]
        if doc.probability != new_prob:
            doc.db_set("probability", new_prob, update_modified=False)


def before_save(doc, method=None):
    """Validate required fields on deal save."""
    if doc.stage in ["Proposal", "Negotiation"] and not doc.get("at_budget_confirmed"):
        frappe.msgprint(
            _("Tip: Please confirm the budget before moving to {0} stage.").format(doc.stage),
            alert=True,
            indicator="orange",
        )


# ────────────────────────────────────────────────────────────
# custom/crm_activity.py  — Activity logging helpers
# ────────────────────────────────────────────────────────────

@frappe.whitelist()
def log_activity(reference_doctype, reference_name, activity_type, subject, notes="", duration=""):
    """
    API endpoint to log a CRM activity (call, email, meeting).

    Usage from client:
        frappe.call({
            method: 'arctic_turns_crm.custom.crm_activity.log_activity',
            args: {
                reference_doctype: 'CRM Lead',
                reference_name: 'CRM-LEAD-0001',
                activity_type: 'Call',
                subject: 'Discovery Call',
                notes: 'Discussed requirements...',
                duration: '30 mins',
            }
        });
    """
    activity = frappe.get_doc({
        "doctype": "CRM Activity",
        "activity_type": activity_type,
        "subject": subject,
        "notes": notes,
        "duration": duration,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "activity_date": nowdate(),
        "done_by": frappe.session.user,
    })
    activity.insert(ignore_permissions=True)
    frappe.db.commit()
    return activity.name


@frappe.whitelist()
def get_timeline(reference_doctype, reference_name):
    """
    Fetch full activity timeline for a Lead or Deal.
    """
    activities = frappe.get_all(
        "CRM Activity",
        filters={
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
        },
        fields=["name", "activity_type", "subject", "notes", "duration", "activity_date", "done_by"],
        order_by="activity_date desc",
    )
    return activities


# ────────────────────────────────────────────────────────────
# tasks.py  — Scheduled background tasks
# ────────────────────────────────────────────────────────────

def send_followup_reminders():
    """
    Daily task: notify reps about overdue follow-ups.
    Runs every day at 9 AM (configured in hooks.py scheduler_events).
    """
    overdue_leads = frappe.get_all(
        "CRM Lead",
        filters={
            "at_next_followup_date": ["<=", today()],
            "status": ["not in", ["Converted", "Lost"]],
        },
        fields=["name", "lead_name", "company", "lead_owner", "at_next_followup_date"],
    )

    # Group by owner
    by_owner = {}
    for lead in overdue_leads:
        owner = lead.lead_owner
        if owner:
            by_owner.setdefault(owner, []).append(lead)

    for owner, leads in by_owner.items():
        email = frappe.db.get_value("User", owner, "email")
        if not email:
            continue

        rows = "".join(
            f"<tr><td>{l.lead_name}</td><td>{l.company}</td><td>{l.at_next_followup_date}</td></tr>"
            for l in leads
        )
        frappe.sendmail(
            recipients=[email],
            subject=f"⏰ {len(leads)} Follow-up(s) Due Today — Arctic Turns CRM",
            message=f"""
            <p>Hi,</p>
            <p>You have <b>{len(leads)}</b> lead(s) requiring follow-up today:</p>
            <table border="1" cellpadding="6" cellspacing="0">
                <thead><tr><th>Lead</th><th>Company</th><th>Due Date</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <p>Log in to Arctic Turns CRM to take action.</p>
            """,
            now=True,
        )

    return f"Sent reminders to {len(by_owner)} rep(s)"


def generate_weekly_pipeline_report():
    """
    Weekly: email pipeline summary to managers.
    """
    stages = ["Discovery", "Demo", "Proposal", "Negotiation", "Closed Won"]
    rows = ""
    total = 0

    for stage in stages:
        deals = frappe.get_all(
            "CRM Deal",
            filters={"stage": stage},
            fields=["name", "deal_name", "currency", "amount"],
        )
        stage_total = sum(d.amount or 0 for d in deals)
        total += stage_total
        rows += f"<tr><td>{stage}</td><td>{len(deals)}</td><td>₹{stage_total:,.0f}</td></tr>"

    managers = frappe.get_all(
        "User", filters={"role_profile_name": "CRM Manager"}, fields=["email"]
    )
    emails = [m.email for m in managers if m.email]

    if emails:
        frappe.sendmail(
            recipients=emails,
            subject="📊 Weekly Pipeline Report — Arctic Turns CRM",
            message=f"""
            <h2>Arctic Turns — Weekly Pipeline Summary</h2>
            <table border="1" cellpadding="8" cellspacing="0">
                <thead><tr><th>Stage</th><th>Deals</th><th>Value</th></tr></thead>
                <tbody>{rows}</tbody>
                <tfoot><tr><td colspan="2"><b>Total</b></td><td><b>₹{total:,.0f}</b></td></tr></tfoot>
            </table>
            <p>Generated: {today()}</p>
            """,
            now=True,
        )


# ────────────────────────────────────────────────────────────
# setup.py  — Run this once to install custom fields
# ────────────────────────────────────────────────────────────

def install_custom_fields():
    """
    Run via bench console:
        bench --site your-site.com execute arctic_turns_crm.setup.install_custom_fields
    """
    from custom.lead import LEAD_CUSTOM_FIELDS
    from custom.opportunity import DEAL_CUSTOM_FIELDS

    all_fields = [
        ("CRM Lead", LEAD_CUSTOM_FIELDS),
        ("CRM Deal", DEAL_CUSTOM_FIELDS),
    ]

    for doctype, fields in all_fields:
        for field in fields:
            if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
                print(f"  [SKIP] {doctype} → {field['fieldname']} already exists")
                continue

            cf = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": doctype,
                **field,
            })
            cf.insert(ignore_permissions=True)
            print(f"  [OK]   {doctype} → {field['fieldname']} created")

    frappe.db.commit()
    print("\n✅ Arctic Turns CRM custom fields installed successfully.")


# ────────────────────────────────────────────────────────────
# client_scripts/lead_form.js  — Client-side form scripts
# ────────────────────────────────────────────────────────────
"""
// Paste this in Frappe → CRM Lead → Customize Form → Client Script

frappe.ui.form.on('CRM Lead', {
    refresh(frm) {
        // Score badge
        if (frm.doc.at_lead_score !== undefined) {
            const score = frm.doc.at_lead_score;
            const color = score >= 75 ? 'green' : score >= 50 ? 'orange' : 'red';
            frm.page.set_indicator(`Score: ${score}/100`, color);
        }

        // Quick log activity button
        frm.add_custom_button('Log Call', () => {
            frappe.prompt([
                { label: 'Subject', fieldname: 'subject', fieldtype: 'Data', reqd: 1 },
                { label: 'Notes', fieldname: 'notes', fieldtype: 'Text' },
                { label: 'Duration', fieldname: 'duration', fieldtype: 'Data', default: '30 mins' },
            ], (values) => {
                frappe.call({
                    method: 'arctic_turns_crm.custom.crm_activity.log_activity',
                    args: {
                        reference_doctype: 'CRM Lead',
                        reference_name: frm.doc.name,
                        activity_type: 'Call',
                        subject: values.subject,
                        notes: values.notes,
                        duration: values.duration,
                    },
                    callback(r) {
                        if (r.message) {
                            frappe.msgprint('Call logged successfully!', 'Success');
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Log Call Activity', 'Log Call');
        }, 'Actions');

        // Convert to Deal
        if (frm.doc.status === 'Qualified' && !frm.doc.__islocal) {
            frm.add_custom_button('Convert to Deal', () => {
                frappe.confirm(
                    `Convert <b>${frm.doc.lead_name}</b> to a Deal?`,
                    () => {
                        frappe.call({
                            method: 'frappe_crm.api.lead.convert_to_deal',
                            args: { lead: frm.doc.name },
                            callback(r) {
                                if (r.message) {
                                    frappe.set_route('Form', 'CRM Deal', r.message);
                                }
                            }
                        });
                    }
                );
            }, 'Actions');
        }
    },

    at_lead_score(frm) {
        // Real-time score color feedback
        const score = frm.doc.at_lead_score;
        if (score > 100) frm.set_value('at_lead_score', 100);
        if (score < 0) frm.set_value('at_lead_score', 0);
    },

    status(frm) {
        if (frm.doc.status === 'Qualified') {
            frappe.msgprint({
                message: 'Great! Consider converting this lead to a Deal.',
                indicator: 'green',
                alert: true,
            });
        }
    }
});
"""

# ────────────────────────────────────────────────────────────
# client_scripts/deal_form.js
# ────────────────────────────────────────────────────────────
"""
// Paste in Frappe → CRM Deal → Customize Form → Client Script

frappe.ui.form.on('CRM Deal', {
    refresh(frm) {
        const prob = frm.doc.probability;
        const color = prob >= 70 ? 'green' : prob >= 40 ? 'orange' : 'red';
        frm.page.set_indicator(`${prob}% probability`, color);

        frm.add_custom_button('Log Meeting', () => {
            frappe.prompt([
                { label: 'Subject', fieldname: 'subject', fieldtype: 'Data', reqd: 1 },
                { label: 'Notes', fieldname: 'notes', fieldtype: 'Text' },
                { label: 'Duration', fieldname: 'duration', fieldtype: 'Data', default: '1 hour' },
            ], (values) => {
                frappe.call({
                    method: 'arctic_turns_crm.custom.crm_activity.log_activity',
                    args: {
                        reference_doctype: 'CRM Deal',
                        reference_name: frm.doc.name,
                        activity_type: 'Meeting',
                        subject: values.subject,
                        notes: values.notes,
                        duration: values.duration,
                    },
                    callback(r) {
                        if (r.message) {
                            frappe.msgprint('Meeting logged!', 'Success');
                            frm.reload_doc();
                        }
                    }
                });
            }, 'Log Meeting', 'Log Meeting');
        }, 'Actions');
    },

    stage(frm) {
        const stageMap = {
            'Discovery': 20, 'Demo': 35, 'Proposal': 55,
            'Negotiation': 75, 'Closed Won': 100, 'Closed Lost': 0
        };
        if (stageMap[frm.doc.stage] !== undefined) {
            frm.set_value('probability', stageMap[frm.doc.stage]);
        }
        if (frm.doc.stage === 'Closed Won') {
            frappe.msgprint({ message: '🎉 Congratulations! Deal won!', indicator: 'green', alert: true });
        }
    }
});
"""

# ────────────────────────────────────────────────────────────
# INSTALLATION GUIDE
# ────────────────────────────────────────────────────────────
"""
STEP-BY-STEP: Installing Arctic Turns CRM on Frappe/ERPNext
===========================================================

1. CREATE THE APP
   ─────────────────
   cd /path/to/frappe-bench
   bench new-app arctic_turns_crm
   # Fill in: Arctic Turns CRM, Arctic Turns, etc.

2. INSTALL ON YOUR SITE
   ─────────────────────
   bench --site your-site.com install-app arctic_turns_crm

3. COPY THE FILES
   ───────────────
   Copy the Python files from this script into:
   apps/arctic_turns_crm/arctic_turns_crm/

4. RUN CUSTOM FIELD INSTALL
   ─────────────────────────
   bench --site your-site.com execute arctic_turns_crm.setup.install_custom_fields

5. ADD CLIENT SCRIPTS
   ────────────────────
   In Frappe UI:
   → Settings → Customize Form → CRM Lead → Client Script
   → Paste lead_form.js content

   → Settings → Customize Form → CRM Deal → Client Script
   → Paste deal_form.js content

6. CONFIGURE SCHEDULED TASKS
   ──────────────────────────
   bench --site your-site.com set-config scheduler_enabled 1
   bench schedule   # start the scheduler

7. MIGRATE
   ─────────
   bench --site your-site.com migrate

8. RESTART
   ────────
   bench restart

FRAPPE CRM MODULES REQUIRED:
   - frappe_crm (install via: bench get-app frappe_crm)
   - erpnext (optional, for full ERP integration)

BENCH COMMANDS REFERENCE:
   bench start                          # Start dev server
   bench --site [site] migrate          # Apply DB changes
   bench --site [site] clear-cache      # Clear cache
   bench --site [site] console          # Python REPL
"""
