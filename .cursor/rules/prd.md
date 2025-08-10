---

# **Project Requirement Document (PRD)**

**Project Name:** JobTrackAI – Job Application Tracking Agent
**Primary Language:** Python
**Core Tech:** OpenAI Agents, Supabase, REST API (FastAPI)

---

## **1. Project Overview**

JobTrackAI is an AI-powered agent that processes user messages and job links, understands their intent, and updates a central job application tracking database.
The system must:

1. Detect job links and prompt the user to provide job details manually.
2. Store job details (role, company, description, status) in Supabase.
3. Understand status updates from natural language.
4. Handle ambiguity by prompting the user for clarification.
5. Include robust error logging for debugging.

---

## **2. User Flow**

### **2.1 New Job Link Input**

1. User sends a message with a job link.
2. Agent detects the link and asks the user to provide: **job_title**, **company_name**, and **job_description** (optional).
3. Agent asks:

   > "Is this a new job you applied to?"
4. On confirmation → Inserts into Supabase with **status = 'applied'**.

---

### **2.2 Status Update Input**

1. User sends a message like:

   * "I got rejected from Google job."
   * "The Microsoft backend role is now in interview stage."
2. Agent parses:

   * Intent = status update.
   * Entity = company/job role.
3. If multiple matching jobs exist:

   > "Which Google job are you referring to?" (List jobs with IDs/titles)
4. Updates corresponding record in Supabase.

---

### **2.3 Ambiguity / Error Handling**

* If link processing is unclear:

  > "I couldn't process the link. Could you paste the role and company name?"
* If user message is unclear:

  > "Could you confirm if this is a new job application or a status update?"

---

## **3. Agent Logic Overview**

### **3.1 Core Capabilities**

* **Intent Classification:** New job vs. status update vs. unclear.
* **Entity Recognition:** Extract company name, job title, job link.
* **Context Handling:** Check for multiple matching records before updating.
* **Link Detection:** Identify when messages include potential job links.

---

### **3.2 OpenAI Agent Configuration**

* **Model:** GPT-4o-mini or GPT-4o (depending on cost/speed trade-off).
* **Tools:**

  * `update_job_status(job_id, status)` → Supabase API call.
  * `insert_new_job(data)` → Supabase API call.
* **Memory:** Maintain short-term conversation context per user.

---

## **4. Technical Architecture**

### **4.1 Components**

1. **FastAPI Backend** – Routes for:

   * `/agent/message` → Passes user message to agent.
   * `/agent/webhook` (future WhatsApp integration).
2. **OpenAI Agent** – Runs intent classification, parsing, and database calls.
3. **Supabase** – PostgreSQL storage + REST API.


---

### **4.2 Database Schema (Supabase)**

**Table:** `jobs`

| Column           | Type        | Description                                                    |
| ---------------- | ----------- | -------------------------------------------------------------- |
| id               | uuid (PK)   | Unique job ID                                                  |
| user\_id         | uuid        | Owner of job entry                                             |
| job\_title       | text        | Job role name                                                  |
| company\_name    | text        | Company name                                                   |
| job\_link        | text        | URL to posting                                                 |
| job\_description | text        | Short summary                                                  |
| status           | text        | Enum: `applied`, `interview`, `offer`, `rejected`, `withdrawn` |
| date\_added      | timestamptz | When job was added                                             |
| last\_updated    | timestamptz | Last status change                                             |

---

## **5. Error Handling & Logging**

* **Types of Errors:**

  
  * **Supabase API Error:** Log payload + returned error.
  * **LLM Misclassification:** Log input + intent + fallback response.
* **Logging:** Structured JSON logs with timestamps.
* **Debug Mode:** Enable verbose logging during development.

---

## **6. Future Extensions (Not in MVP)**

* Resume tailoring for ATS.
* Keyword matching between job description and resume.
* Multi-user authentication for personal dashboards.
* Automatic company research summaries.

---

## **7. MVP Scope**

✅ Intent classification (new job vs. status update).
✅ Manual job detail entry when a link is shared.
✅ Supabase integration (insert/update records).
✅ Clarification prompts for ambiguity.
✅ Robust error handling & logging.

❌ No WhatsApp integration yet.
❌ No advanced ATS resume matching.

---

## **8. Example Interactions**

**Example 1 – New Job**

```
User: Here's a role at Microsoft: https://www.linkedin.com/jobs/view/123456
Agent: Is this a new job you applied to?
User: Yes
Agent: Added 'Software Engineer' at Microsoft with status 'applied'.
```

**Example 2 – Status Update**

```
User: I got rejected from Google job.
Agent: I found 2 Google jobs in your list. Which one do you mean?
1. Frontend Developer
2. Data Scientist
User: 2
Agent: Updated 'Data Scientist' at Google to status 'rejected'.
```

---