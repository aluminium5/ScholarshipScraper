export type Level = 'school' | 'ug' | 'pg' | 'phd' | 'any'

export type AppStatus = 'saved' | 'applied' | 'under_review' | 'awarded' | 'rejected'

export interface User {
  id: number
  name: string
  email: string
  created_at: string
  is_admin: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Scholarship {
  id: number
  source: string
  external_id: string
  title: string
  provider: string | null
  description: string | null
  award_amount: string | null
  eligibility: string | null
  level: Level
  tags: string[]
  opens_at: string | null
  deadline: string | null
  apply_url: string
  info_url: string | null
  is_active: boolean
  last_seen_at: string | null
  days_left: number | null
  application_status: AppStatus | null
  application_id: number | null
}

export interface ScholarshipList {
  items: Scholarship[]
  total: number
}

export interface SourceCount {
  source: string
  count: number
}

export interface ScholarshipMeta {
  sources: SourceCount[]
  levels: SourceCount[]
  tags: SourceCount[]
  total_active: number
  closing_this_week: number
  expired_hidden: number
  last_refresh_at: string | null
  last_refresh_summary: Record<string, unknown>
}

export interface Application {
  id: number
  scholarship_id: number
  status: AppStatus
  applied_on: string | null
  notes: string | null
  updated_at: string
  scholarship: Scholarship | null
}

export interface DocumentItem {
  have: boolean
  expires_on: string | null
  note: string | null
}

export interface Portfolio {
  personal: {
    full_name: string | null
    dob: string | null
    gender: string | null
    phone: string | null
    email: string | null
    address: string | null
    state: string | null
    district: string | null
    category: string | null
    religion: string | null
    disability_status: string | null
  }
  academic: {
    current_course: string | null
    institution: string | null
    year_or_semester: string | null
    cgpa_or_percentage: string | null
    class_10_percentage: string | null
    class_12_percentage: string | null
    roll_or_enrollment_no: string | null
  }
  family: {
    father_name: string | null
    father_occupation: string | null
    mother_name: string | null
    mother_occupation: string | null
    annual_family_income: string | null
  }
  bank: {
    account_holder_name: string | null
    bank_name: string | null
    ifsc: string | null
    /** Last four digits only — full account numbers are never stored. */
    account_last4: string | null
  }
  documents: Record<string, DocumentItem>
  cv: {
    summary: string | null
    skills: string[]
    projects: string[]
    achievements: string[]
    extracurriculars: string[]
    github: string | null
    linkedin: string | null
    other_links: string[]
  }
  updated_at: string | null
}

export interface RefreshResult {
  ok: boolean
  trigger: string
  started_at: string
  finished_at: string | null
  summary: Record<string, unknown>
}
