// Types mirroring the backend Pydantic schemas.

export type Role = "admin" | "operator";

export interface Auth {
  id: number;
  email: string;
  role: Role;
  csrf_token: string;
  must_change_password: boolean;
  two_factor_required?: boolean;
  two_factor_enabled?: boolean;
  permissions?: string[];
}

export interface PermissionInfo {
  key: string;
  label: string;
}

export interface TotpSetup {
  secret: string;
  otpauth_uri: string;
  qr_data_uri: string;
}

export type ReportStatus = "new" | "reviewing" | "malicious" | "benign" | "closed";

export interface ReportedEmail {
  id: number;
  reporter_email: string | null;
  subject: string | null;
  sender: string | null;
  body_preview: string | null;
  source: string;
  is_simulation: boolean;
  matched_rid: string | null;
  status: ReportStatus;
  notes: string | null;
  created_at: string;
}

export interface ReportedSummary {
  total: number;
  new: number;
  simulations: number;
  real: number;
}

export interface AddinConfig {
  token: string;
  manifest_url: string;
  taskpane_url: string;
  gmail_script_url: string;
}

export type Difficulty = "beginner" | "intermediate" | "advanced";
export type EnrollmentStatus = "assigned" | "in_progress" | "completed" | "failed";

export interface QuizQuestion {
  id?: number;
  prompt: string;
  options: string[];
  correct_index: number;
  order?: number;
}

export interface TrainingModule {
  id: number;
  title: string;
  description: string | null;
  category: string;
  difficulty: Difficulty;
  content_html: string;
  video_url: string | null;
  estimated_minutes: number;
  pass_score: number;
  points: number;
  is_published: boolean;
  questions: QuizQuestion[];
  enrolled: number;
  completed: number;
}

export interface TrainingEnrollment {
  id: number;
  module_id: number;
  module_title: string;
  email: string;
  token: string;
  status: EnrollmentStatus;
  score: number | null;
  attempts: number;
  assigned_at: string;
  completed_at: string | null;
}

export interface LeaderboardRow {
  email: string;
  points: number;
  completed: number;
}

export interface TrainingSummary {
  modules: number;
  enrollments: number;
  completed: number;
  completion_rate: number;
}

export interface RecommendationRow {
  email: string;
  risk: "low" | "medium" | "high";
  next_sim_difficulty: Difficulty;
  recommended_training_difficulty: Difficulty;
  targeted: number;
  failed: number;
}

export interface AutoEnrollConfig {
  enabled: boolean;
  mode: "adaptive" | "fixed";
  module_id: number | null;
}

export interface SsoInfo {
  enabled: boolean;
  button_label: string;
}

export interface Benchmark {
  enabled: boolean;
  industry: string;
  baseline_click_rate: number;
  baseline_report_rate: number;
  your_click_rate: number;
  your_report_rate: number;
  sample: number;
}

export interface BenchmarkSettings {
  enabled: boolean;
  industry: string;
  baseline_click_rate: number;
  baseline_report_rate: number;
}

export interface SsoSettings {
  enabled: boolean;
  issuer: string;
  client_id: string;
  allowed_domains: string;
  auto_provision: boolean;
  button_label: string;
  has_secret: boolean;
  redirect_uri: string;
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
  channel: "email";
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
  is_vip?: boolean;
}

export interface AttackSurfacePerson {
  email: string;
  targeted: number;
  failed: number;
  is_vip: boolean;
  risk: "low" | "medium" | "high";
}

export interface AttackSurface {
  people: AttackSurfacePerson[];
  vip_count: number;
  vip_failed: number;
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

export interface GeoPoint {
  country: string;
  code: string;
  count: number;
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

export interface AiSettings {
  provider: string;
  model: string;
  has_key: boolean;
  key_hint: string;
  providers: { value: string; label: string }[];
}

export interface ImapSettings {
  enabled: boolean;
  host: string;
  port: number;
  username: string;
  ssl: boolean;
  folder: string;
  has_password: boolean;
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
  permissions: string[];
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
  last_status: number | null;
  last_error: string | null;
  last_attempt_at: string | null;
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

export interface AllowlistSection {
  platform: string;
  where: string;
  entries: string[];
  steps: string[];
  warning: string | null;
}

export interface AllowlistResult {
  sections: AllowlistSection[];
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
  channel: "email";
  template_id: number;
  profile_id: number | null;
  group_id: number;
  page_id: number | null;
  phish_url: string;
  redirect_url: string | null;
  authorized_by?: string | null;
  authorization_ref?: string | null;
  created_at: string;
  launch_at: string | null;
  send_by_at: string | null;
  completed_at: string | null;
  auto_enroll_trigger?: string;
  auto_enroll_module_id?: number | null;
  auto_enroll_email?: boolean;
  send_jitter?: boolean;
  business_hours_only?: boolean;
  send_timezone?: string;
}

export interface Person {
  email: string;
  first_name: string | null;
  last_name: string | null;
  targeted: number;
  opened: number;
  clicked: number;
  submitted: number;
  reported: number;
  trainings_assigned: number;
  trainings_completed: number;
  last_activity: string | null;
  risk: "high" | "medium" | "low";
}

export interface CampaignStats {
  total: number;
  sent: number;
  opened: number;
  clicked: number;
  submitted: number;
  reported: number;
  error: number;
  attachments_opened: number;
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
  attachment_opened_at: string | null;
}

export interface CampaignDetail extends Campaign {
  stats: CampaignStats;
  results: Result[];
  target_group_ids: number[];
  exclude_group_ids: number[];
}

export interface EventItem {
  id: number;
  rid: string | null;
  type: string;
  ip: string | null;
  created_at: string;
}
