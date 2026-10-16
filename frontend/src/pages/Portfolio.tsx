import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { CopyButton } from '../components/CopyButton'
import { ErrorNote, Spinner } from '../components/Spinner'
import { request } from '../lib/api'
import type { Portfolio } from '../types'

type TabKey = 'personal' | 'academic' | 'family' | 'bank' | 'documents' | 'cv'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'personal', label: 'Personal' },
  { key: 'academic', label: 'Academic' },
  { key: 'family', label: 'Family & income' },
  { key: 'bank', label: 'Bank' },
  { key: 'documents', label: 'Documents' },
  { key: 'cv', label: 'CV' },
]

const DOCUMENTS: { key: string; label: string }[] = [
  { key: 'aadhaar', label: 'Aadhaar card' },
  { key: 'income_certificate', label: 'Income certificate' },
  { key: 'caste_certificate', label: 'Caste certificate' },
  { key: 'domicile', label: 'Domicile certificate' },
  { key: 'marksheets', label: 'Marksheets' },
  { key: 'fee_receipt', label: 'Fee receipt' },
  { key: 'bonafide', label: 'Bonafide certificate' },
  { key: 'bank_passbook', label: 'Bank passbook' },
  { key: 'photo', label: 'Passport photo' },
]

/** The shape the API accepts: the server-managed timestamp is not sent back. */
type PortfolioDraft = Omit<Portfolio, 'updated_at'>

const EMPTY: PortfolioDraft = {
  personal: {
    full_name: null,
    dob: null,
    gender: null,
    phone: null,
    email: null,
    address: null,
    state: null,
    district: null,
    category: null,
    religion: null,
    disability_status: null,
  },
  academic: {
    current_course: null,
    institution: null,
    year_or_semester: null,
    cgpa_or_percentage: null,
    class_10_percentage: null,
    class_12_percentage: null,
    roll_or_enrollment_no: null,
  },
  family: {
    father_name: null,
    father_occupation: null,
    mother_name: null,
    mother_occupation: null,
    annual_family_income: null,
  },
  bank: {
    account_holder_name: null,
    bank_name: null,
    ifsc: null,
    account_last4: null,
  },
  documents: {},
  cv: {
    summary: null,
    skills: [],
    projects: [],
    achievements: [],
    extracurriculars: [],
    github: null,
    linkedin: null,
    other_links: [],
  },
}

/** Blank strings are sent as null so the API stores a real absence. */
function blankToNull(value: string): string | null {
  return value.trim() === '' ? null : value
}

function linesToList(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

interface FieldProps {
  label: string
  value: string | null
  onChange: (value: string | null) => void
  type?: string
  placeholder?: string
  hint?: string
  maxLength?: number
}

/** A labelled input with a Copy button, which is the point of this page. */
function Field({ label, value, onChange, type = 'text', placeholder, hint, maxLength }: FieldProps) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-center gap-1.5">
        <input
          type={type}
          className="input"
          value={value ?? ''}
          placeholder={placeholder}
          maxLength={maxLength}
          onChange={(event) => onChange(blankToNull(event.target.value))}
        />
        <CopyButton value={value} label={label} />
      </div>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  )
}

function TextAreaField({
  label,
  value,
  onChange,
  rows = 4,
  hint,
  placeholder,
}: {
  label: string
  value: string | null
  onChange: (value: string | null) => void
  rows?: number
  hint?: string
  placeholder?: string
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-start gap-1.5">
        <textarea
          className="input"
          rows={rows}
          value={value ?? ''}
          placeholder={placeholder}
          onChange={(event) => onChange(blankToNull(event.target.value))}
        />
        <CopyButton value={value} label={label} />
      </div>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  )
}

function ListField({
  label,
  values,
  onChange,
  hint,
}: {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  hint?: string
}) {
  const text = values.join('\n')
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-start gap-1.5">
        <textarea
          className="input"
          rows={4}
          value={text}
          placeholder="One per line"
          onChange={(event) => onChange(linesToList(event.target.value))}
        />
        <CopyButton value={text || null} label={label} />
      </div>
      <p className="mt-1 text-xs text-slate-500">{hint ?? 'One per line.'}</p>
    </div>
  )
}

export function PortfolioPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<TabKey>('personal')
  const [draft, setDraft] = useState<PortfolioDraft | null>(null)
  const [saved, setSaved] = useState(false)

  const portfolio = useQuery({
    queryKey: ['portfolio'],
    queryFn: () => request<Portfolio>('/portfolio'),
  })

  // Seed the editable draft once the saved portfolio arrives.
  useEffect(() => {
    if (!portfolio.data) return
    const { updated_at: _ignored, ...rest } = portfolio.data
    setDraft({
      personal: { ...EMPTY.personal, ...rest.personal },
      academic: { ...EMPTY.academic, ...rest.academic },
      family: { ...EMPTY.family, ...rest.family },
      bank: { ...EMPTY.bank, ...rest.bank },
      documents: rest.documents ?? {},
      cv: { ...EMPTY.cv, ...rest.cv },
    })
  }, [portfolio.data])

  const save = useMutation({
    mutationFn: (body: PortfolioDraft) =>
      request<Portfolio>('/portfolio', { method: 'PUT', body }),
    onSuccess: (result) => {
      queryClient.setQueryData(['portfolio'], result)
      setSaved(true)
      window.setTimeout(() => setSaved(false), 2000)
    },
  })

  const dirty = useMemo(() => {
    if (!draft || !portfolio.data) return false
    const { updated_at: _ignored, ...rest } = portfolio.data
    return JSON.stringify(draft) !== JSON.stringify(rest)
  }, [draft, portfolio.data])

  if (portfolio.isLoading) return <Spinner label="Loading your portfolio" />
  if (portfolio.isError) return <ErrorNote error={portfolio.error} />
  if (!draft) return <Spinner label="Preparing the form" />

  /** Patch one section of the draft. */
  function patch<K extends keyof PortfolioDraft>(
    section: K,
    changes: Partial<PortfolioDraft[K]>,
  ) {
    setDraft((current) =>
      current === null
        ? current
        : { ...current, [section]: { ...current[section], ...changes } },
    )
  }

  function setDocument(key: string, have: boolean, expires: string | null) {
    setDraft((current) => {
      if (current === null) return current
      const documents = { ...current.documents }
      if (!have && !expires) delete documents[key]
      else documents[key] = { have, expires_on: expires, note: null }
      return { ...current, documents }
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Your portfolio
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            The details every application form asks for. Use the copy buttons to paste
            them straight into a form.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {saved ? (
            <span className="text-sm font-medium text-emerald-600">Saved</span>
          ) : dirty ? (
            <span className="text-sm text-slate-500">Unsaved changes</span>
          ) : null}
          <button
            type="button"
            onClick={() => save.mutate(draft)}
            disabled={save.isPending || !dirty}
            className="btn-primary"
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      {save.isError ? <ErrorNote error={save.error} /> : null}

      <div className="border-b border-slate-200">
        <nav className="-mb-px flex flex-wrap gap-1" aria-label="Portfolio sections">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              aria-current={tab === item.key ? 'page' : undefined}
              className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                tab === item.key
                  ? 'border-accent-600 text-accent-700'
                  : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="card p-4 sm:p-6">
        {tab === 'personal' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Full name"
              value={draft.personal.full_name}
              onChange={(v) => patch('personal', { full_name: v })}
            />
            <Field
              label="Date of birth"
              type="date"
              value={draft.personal.dob}
              onChange={(v) => patch('personal', { dob: v })}
            />
            <Field
              label="Gender"
              value={draft.personal.gender}
              onChange={(v) => patch('personal', { gender: v })}
            />
            <Field
              label="Phone"
              type="tel"
              value={draft.personal.phone}
              onChange={(v) => patch('personal', { phone: v })}
            />
            <Field
              label="Email"
              type="email"
              value={draft.personal.email}
              onChange={(v) => patch('personal', { email: v })}
            />
            <Field
              label="Category"
              value={draft.personal.category}
              onChange={(v) => patch('personal', { category: v })}
              placeholder="General / OBC / SC / ST"
            />
            <Field
              label="State"
              value={draft.personal.state}
              onChange={(v) => patch('personal', { state: v })}
            />
            <Field
              label="District"
              value={draft.personal.district}
              onChange={(v) => patch('personal', { district: v })}
            />
            <Field
              label="Religion (optional)"
              value={draft.personal.religion}
              onChange={(v) => patch('personal', { religion: v })}
            />
            <Field
              label="Disability status"
              value={draft.personal.disability_status}
              onChange={(v) => patch('personal', { disability_status: v })}
              placeholder="None / type and percentage"
            />
            <div className="sm:col-span-2">
              <TextAreaField
                label="Address"
                rows={3}
                value={draft.personal.address}
                onChange={(v) => patch('personal', { address: v })}
              />
            </div>
          </div>
        ) : null}

        {tab === 'academic' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Current course"
              value={draft.academic.current_course}
              onChange={(v) => patch('academic', { current_course: v })}
              placeholder="B.Tech Computer Science"
            />
            <Field
              label="Institution"
              value={draft.academic.institution}
              onChange={(v) => patch('academic', { institution: v })}
            />
            <Field
              label="Year or semester"
              value={draft.academic.year_or_semester}
              onChange={(v) => patch('academic', { year_or_semester: v })}
            />
            <Field
              label="CGPA or percentage"
              value={draft.academic.cgpa_or_percentage}
              onChange={(v) => patch('academic', { cgpa_or_percentage: v })}
            />
            <Field
              label="Class 10 percentage"
              value={draft.academic.class_10_percentage}
              onChange={(v) => patch('academic', { class_10_percentage: v })}
            />
            <Field
              label="Class 12 percentage"
              value={draft.academic.class_12_percentage}
              onChange={(v) => patch('academic', { class_12_percentage: v })}
            />
            <Field
              label="Roll or enrollment number"
              value={draft.academic.roll_or_enrollment_no}
              onChange={(v) => patch('academic', { roll_or_enrollment_no: v })}
            />
          </div>
        ) : null}

        {tab === 'family' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Father's name"
              value={draft.family.father_name}
              onChange={(v) => patch('family', { father_name: v })}
            />
            <Field
              label="Father's occupation"
              value={draft.family.father_occupation}
              onChange={(v) => patch('family', { father_occupation: v })}
            />
            <Field
              label="Mother's name"
              value={draft.family.mother_name}
              onChange={(v) => patch('family', { mother_name: v })}
            />
            <Field
              label="Mother's occupation"
              value={draft.family.mother_occupation}
              onChange={(v) => patch('family', { mother_occupation: v })}
            />
            <Field
              label="Annual family income"
              value={draft.family.annual_family_income}
              onChange={(v) => patch('family', { annual_family_income: v })}
              placeholder="250000"
              hint="As written on your income certificate."
            />
          </div>
        ) : null}

        {tab === 'bank' ? (
          <div className="space-y-4">
            <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-sm text-slate-700">
                Only the last four digits of your account number are stored. Keep the
                full number and your Aadhaar number out of this app.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Account holder name"
                value={draft.bank.account_holder_name}
                onChange={(v) => patch('bank', { account_holder_name: v })}
              />
              <Field
                label="Bank name"
                value={draft.bank.bank_name}
                onChange={(v) => patch('bank', { bank_name: v })}
              />
              <Field
                label="IFSC"
                value={draft.bank.ifsc}
                onChange={(v) => patch('bank', { ifsc: v })}
                maxLength={11}
                placeholder="SBIN0001234"
              />
              <Field
                label="Account number — last 4 digits"
                value={draft.bank.account_last4}
                onChange={(v) => patch('bank', { account_last4: v })}
                maxLength={4}
                placeholder="4321"
                hint="Four digits only."
              />
            </div>
          </div>
        ) : null}

        {tab === 'documents' ? (
          <div className="space-y-1">
            <p className="mb-3 text-sm text-slate-600">
              Tick what you already have, and note an expiry date where one applies.
              Do not type document numbers here.
            </p>
            <ul className="divide-y divide-slate-100">
              {DOCUMENTS.map((document) => {
                const entry = draft.documents[document.key]
                const have = entry?.have ?? false
                const expires = entry?.expires_on ?? null
                return (
                  <li
                    key={document.key}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <label className="flex items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={have}
                        onChange={(event) =>
                          setDocument(document.key, event.target.checked, expires)
                        }
                        className="h-4 w-4 rounded border-slate-300 text-accent-600 focus:ring-accent-500"
                      />
                      <span className="text-sm text-slate-800">{document.label}</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-slate-500" htmlFor={`exp-${document.key}`}>
                        Expires
                      </label>
                      <input
                        id={`exp-${document.key}`}
                        type="date"
                        value={expires ?? ''}
                        onChange={(event) =>
                          setDocument(
                            document.key,
                            have || Boolean(event.target.value),
                            blankToNull(event.target.value),
                          )
                        }
                        className="input w-auto py-1.5 text-sm"
                      />
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        ) : null}

        {tab === 'cv' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <TextAreaField
                label="Summary"
                rows={3}
                value={draft.cv.summary}
                onChange={(v) => patch('cv', { summary: v })}
                placeholder="Two or three lines about yourself."
              />
            </div>
            <ListField
              label="Skills"
              values={draft.cv.skills}
              onChange={(values) => patch('cv', { skills: values })}
            />
            <ListField
              label="Projects"
              values={draft.cv.projects}
              onChange={(values) => patch('cv', { projects: values })}
            />
            <ListField
              label="Achievements"
              values={draft.cv.achievements}
              onChange={(values) => patch('cv', { achievements: values })}
            />
            <ListField
              label="Extracurriculars"
              values={draft.cv.extracurriculars}
              onChange={(values) => patch('cv', { extracurriculars: values })}
            />
            <Field
              label="GitHub"
              value={draft.cv.github}
              onChange={(v) => patch('cv', { github: v })}
              placeholder="https://github.com/username"
            />
            <Field
              label="LinkedIn"
              value={draft.cv.linkedin}
              onChange={(v) => patch('cv', { linkedin: v })}
              placeholder="https://linkedin.com/in/username"
            />
            <div className="sm:col-span-2">
              <ListField
                label="Other links"
                values={draft.cv.other_links}
                onChange={(values) => patch('cv', { other_links: values })}
              />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
