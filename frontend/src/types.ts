// Types mirroring the backend Pydantic schemas.

export type Role = "admin" | "operator";

export interface Auth {
  id: number;
  email: string;
  role: Role;
  csrf_token: string;
  must_change_password: boolean;
}

export interface Attachment {
  id: number;
  filename: string;
  content_type: string;
  size: number;
}

export interface Template {
  id: number;
  name: string;
  channel: "email" | "sms";
  subject: string;
  envelope_sender: string | null;
  html: string | null;
  text: string | null;
  created_at: string;
  modified_at: string;
  attachments?: Attachment[];
}

export interface Target {
  id?: number;
  email: string;
  phone?: string | null;
  first_name: string | null;
  last_name: string | null;
  position: string | null;
}

export type SmsProviderKind = "console" | "textbelt" | "twilio" | "generic";

export interface SmsProfile {
  id: number;
  name: string;
  provider: SmsProviderKind;
  from_number: string | null;
  account: string | null;
  config: string | null;
  has_secret: boolean;
  created_at: string;
  modified_at: string;
}

export interface GroupSummary {
  id: number;
  name: string;
  target_count: number;
  modified_at: string;
}

export interface Group {
  id: number;
  name: string;
  created_at: string;
  modified_at: string;
  targets: Target[];
}

export interface HeaderItem {
  key: string;
  value: string;
}

export type ProfileKind = "smtp" | "api";
export type ApiProvider = "sendgrid" | "brevo" | "resend" | "mailgun" | "postmark";

export interface Profile {
  id: number;
  name: string;
  from_address: string;
  envelope_sender: string | null;
  kind: ProfileKind;
  host: string | null;
  port: number | null;
  username: string | null;
  headers: HeaderItem[];
  use_starttls: boolean;
  use_ssl: boolean;
  ignore_cert_errors: boolean;
  api_provider: ApiProvider | null;
  api_domain: string | null;
  has_password: boolean;
  has_api_key: boolean;
  created_at: string;
  modified_at: string;
}

export interface RuntimeSettings {
  mail_backend: string;
  capture_passwords: boolean;
  env: string;
}

export interface TimelinePoint {
  date: string;
  sent: number;
  opened: number;
  clicked: number;
  submitted: number;
}

export interface AtRiskUser {
  email: string;
  clicked: number;
  submitted: number;
  total: number;
}

export interface Champion {
  email: string;
  reported: number;
  total: number;
}

export interface RiskUser {
  email: string;
  department: string;
  score: number;
  level: string;
  targeted: number;
  clicked: number;
  submitted: number;
  reported: number;
}

export interface RiskDept {
  name: string;
  score: number;
  level: string;
  people: number;
}

export interface RiskOut {
  overall_score: number;
  overall_level: string;
  total_people: number;
  departments: RiskDept[];
  top_users: RiskUser[];
}

export interface AiTemplate {
  name: string;
  subject: string;
  html: string | null;
  text: string | null;
}

export interface DashboardData {
  campaigns: { total: number; active: number; completed: number; draft: number; scheduled: number };
  funnel: {
    recipients: number;
    sent: number;
    opened: number;
    clicked: number;
    submitted: number;
    reported: number;
    trained: number;
    error: number;
  };
  counts: { templates: number; groups: number; profiles: number; pages: number };
}

export interface AdminUser {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TemplateImportResult {
  subject: string;
  envelope_sender: string | null;
  html: string | null;
  text: string | null;
}

export interface Webhook {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
  has_secret: boolean;
  format: string;
  created_at: string;
  modified_at: string;
}

export interface DeliverabilityCheck {
  key: string;
  label: string;
  status: string;
  record: string | null;
  note: string;
}

export interface DeliverabilityResult {
  domain: string;
  verdict: string;
  summary: string;
  passed: number;
  checks: DeliverabilityCheck[];
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface LandingPage {
  id: number;
  name: string;
  html: string;
  redirect_url: string | null;
  created_at: string;
  modified_at: string;
}

export interface PageSummary {
  id: number;
  name: string;
  redirect_url: string | null;
  modified_at: string;
}

export type CampaignStatus =
  | "draft"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "error";

export type ResultStatus =
  | "scheduled"
  | "sending"
  | "sent"
  | "opened"
  | "clicked"
  | "submitted"
  | "reported"
  | "error";

export interface Campaign {
  id: number;
  name: string;
  status: CampaignStatus;
  channel: "email" | "sms";
  template_id: number;
  profile_id: number | null;
  sms_profile_id: number | null;
  group_id: number;
  page_id: number | null;
  phish_url: string;
  redirect_url: string | null;
  created_at: string;
  launch_at: string | null;
  send_by_at: string | null;
  completed_at: string | null;
}

export interface CampaignStats {
  total: number;
  sent: number;
  opened: number;
  clicked: number;
  submitted: number;
  reported: number;
  error: number;
}

export interface Result {
  id: number;
  rid: string;
  short_code: string | null;
  email: string;
  phone: string | null;
  first_name: string | null;
  last_name: string | null;
  position: string | null;
  status: ResultStatus;
  send_error: string | null;
  sent_at: string | null;
  last_event_at: string | null;
}

export interface CampaignDetail extends Campaign {
  stats: CampaignStats;
  results: Result[];
}

export interface EventItem {
  id: number;
  rid: string | null;
  type: string;
  ip: string | null;
  created_at: string;
}
