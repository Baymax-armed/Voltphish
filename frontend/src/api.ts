// Thin fetch wrapper: same-origin cookies + CSRF header on mutations.
import type {
  AdminUser,
  ApiKey,
  ApiKeyCreated,
  AiTemplate,
  AllowlistResult,
  AtRiskUser,
  AttackSurface,
  Benchmark,
  BenchmarkSettings,
  Champion,
  DeliverabilityResult,
  GeoPoint,
  RiskOut,
  Attachment,
  Auth,
  Campaign,
  CampaignDetail,
  DashboardData,
  EventItem,
  Group,
  GroupSummary,
  Target,
  LandingPage,
  PageSummary,
  Profile,
  AiSettings,
  AddinConfig,
  AutoEnrollConfig,
  ImapSettings,
  LeaderboardRow,
  PermissionInfo,
  Person,
  RecommendationRow,
  ReportedEmail,
  ReportedSummary,
  RuntimeSettings,
  SsoInfo,
  SsoSettings,
  TrainingEnrollment,
  TrainingModule,
  TrainingSummary,
  Template,
  TemplateImportResult,
  TimelinePoint,
  TotpSetup,
  Webhook,
} from "./types";

let csrfToken = "";
export function setCsrfToken(token: string) {
  csrfToken = token;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const opts: RequestInit = { method, headers, credentials: "same-origin" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  if (!["GET", "HEAD"].includes(method)) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const resp = await fetch(`/api/v1${path}`, opts);
  if (resp.status === 204) return undefined as T;

  let data: any = null;
  const text = await resp.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!resp.ok) {
    const detail =
      (data && (data.detail || (Array.isArray(data) && data[0]?.msg))) ||
      `Request failed (${resp.status})`;
    throw new ApiError(resp.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export const api = {
  // auth
  login: (email: string, password: string, code?: string) =>
    request<Auth>("POST", "/auth/login", { email, password, code: code || null }),
  logout: () => request<{ detail: string }>("POST", "/auth/logout"),
  me: () => request<Auth>("GET", "/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("POST", "/auth/change-password", { current_password, new_password }),

  // reported emails (report-phish add-in triage)
  listReported: (onlyReal = false) =>
    request<ReportedEmail[]>("GET", `/reported${onlyReal ? "?only_real=true" : ""}`),
  reportedSummary: () => request<ReportedSummary>("GET", "/reported/summary"),
  updateReported: (id: number, p: { status?: string; notes?: string }) =>
    request<ReportedEmail>("PATCH", `/reported/${id}`, p),
  deleteReported: (id: number) => request<{ detail: string }>("DELETE", `/reported/${id}`),
  addinConfig: () => request<AddinConfig>("GET", "/reported/addin/config"),
  regenerateAddinToken: () => request<AddinConfig>("POST", "/reported/addin/regenerate"),

  // training LMS
  listModules: () => request<TrainingModule[]>("GET", "/training/modules"),
  createModule: (m: Record<string, unknown>) => request<TrainingModule>("POST", "/training/modules", m),
  updateModule: (id: number, m: Record<string, unknown>) =>
    request<TrainingModule>("PUT", `/training/modules/${id}`, m),
  deleteModule: (id: number) => request<{ detail: string }>("DELETE", `/training/modules/${id}`),
  assignModule: (id: number, p: { emails?: string[]; group_id?: number | null; campaign_id?: number | null; outcome?: string }) =>
    request<{ detail: string }>("POST", `/training/modules/${id}/assign`, p),
  trainingAudience: (p: { campaign_id: number; outcome: string }) =>
    request<{ count: number; total: number }>("POST", "/training/audience", p),
  sendTrainingInvites: (id: number, p: { profile_id: number; only_pending?: boolean }) =>
    request<{ detail: string }>("POST", `/training/modules/${id}/send`, p),
  listEnrollments: (moduleId?: number) =>
    request<TrainingEnrollment[]>("GET", `/training/enrollments${moduleId ? `?module_id=${moduleId}` : ""}`),
  trainingLeaderboard: () => request<LeaderboardRow[]>("GET", "/training/leaderboard"),
  trainingSummary: () => request<TrainingSummary>("GET", "/training/summary"),
  trainingRecommendations: () => request<RecommendationRow[]>("GET", "/training/recommendations"),
  getAutoEnroll: () => request<AutoEnrollConfig>("GET", "/training/auto-enroll"),
  updateAutoEnroll: (p: AutoEnrollConfig) => request<AutoEnrollConfig>("PUT", "/training/auto-enroll", p),

  // SSO (OIDC)
  ssoInfo: () => request<SsoInfo>("GET", "/auth/sso/info"),
  getSsoSettings: () => request<SsoSettings>("GET", "/settings/sso"),
  updateSsoSettings: (p: Record<string, unknown>) => request<SsoSettings>("PUT", "/settings/sso", p),

  // two-factor auth (TOTP)
  totpStatus: () => request<{ enabled: boolean }>("GET", "/auth/2fa/status"),
  totpSetup: () => request<TotpSetup>("POST", "/auth/2fa/setup"),
  totpEnable: (code: string) => request<{ enabled: boolean }>("POST", "/auth/2fa/enable", { code }),
  totpDisable: (code: string) => request<{ enabled: boolean }>("POST", "/auth/2fa/disable", { code }),

  // users (admin)
  listUsers: () => request<AdminUser[]>("GET", "/users"),
  listPermissions: () => request<PermissionInfo[]>("GET", "/users/permissions"),
  createUser: (u: Record<string, unknown>) => request<AdminUser>("POST", "/users", u),
  updateUser: (id: number, u: Record<string, unknown>) => request<AdminUser>("PUT", `/users/${id}`, u),
  resetUserPassword: (id: number, password: string) =>
    request<{ detail: string }>("POST", `/users/${id}/reset-password`, { password }),
  deleteUser: (id: number) => request<{ detail: string }>("DELETE", `/users/${id}`),

  // templates
  listTemplates: () => request<Template[]>("GET", "/templates"),
  createTemplate: (t: Partial<Template>) => request<Template>("POST", "/templates", t),
  importTemplate: (raw: string) => request<TemplateImportResult>("POST", "/templates/import", { raw }),
  addAttachment: (templateId: number, a: { filename: string; content_type: string; content_b64: string }) =>
    request<Attachment>("POST", `/templates/${templateId}/attachments`, a),
  deleteAttachment: (templateId: number, id: number) =>
    request<{ detail: string }>("DELETE", `/templates/${templateId}/attachments/${id}`),

  // landing page import-from-URL
  importSite: (url: string) => request<{ url: string; html: string }>("POST", "/pages/import-site", { url }),
  aiGeneratePage: (scenario: string) => request<{ name: string; html: string }>("POST", "/pages/ai-generate", { scenario }),
  updateTemplate: (id: number, t: Partial<Template>) =>
    request<Template>("PUT", `/templates/${id}`, t),
  deleteTemplate: (id: number) => request<{ detail: string }>("DELETE", `/templates/${id}`),

  // groups
  listGroups: () => request<GroupSummary[]>("GET", "/groups"),
  getGroup: (id: number) => request<Group>("GET", `/groups/${id}`),
  createGroup: (g: { name: string; targets: unknown[] }) => request<Group>("POST", "/groups", g),
  updateGroup: (id: number, g: { name: string; targets: unknown[] }) =>
    request<Group>("PUT", `/groups/${id}`, g),
  deleteGroup: (id: number) => request<{ detail: string }>("DELETE", `/groups/${id}`),
  parseXlsx: async (file: File): Promise<Target[]> => {
    const fd = new FormData();
    fd.append("file", file);
    const resp = await fetch(`/api/v1/groups/parse-xlsx`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": csrfToken },
      body: fd,
    });
    const text = await resp.text();
    const data = text ? JSON.parse(text) : [];
    if (!resp.ok) throw new ApiError(resp.status, data?.detail || "Couldn't read that file");
    return data as Target[];
  },

  // profiles
  listProfiles: () => request<Profile[]>("GET", "/profiles"),
  createProfile: (p: Record<string, unknown>) => request<Profile>("POST", "/profiles", p),
  updateProfile: (id: number, p: Record<string, unknown>) =>
    request<Profile>("PUT", `/profiles/${id}`, p),
  deleteProfile: (id: number) => request<{ detail: string }>("DELETE", `/profiles/${id}`),
  verifyProfile: (id: number) => request<{ detail: string }>("POST", `/profiles/${id}/verify`),

  // runtime settings (for dev-mode banner)
  getSettings: () => request<RuntimeSettings>("GET", "/settings"),

  // AI provider config (admin)
  getAiSettings: () => request<AiSettings>("GET", "/settings/ai"),
  updateAiSettings: (p: Record<string, unknown>) => request<AiSettings>("PUT", "/settings/ai", p),
  testAiSettings: () => request<{ detail: string }>("POST", "/settings/ai/test"),

  getImapSettings: () => request<ImapSettings>("GET", "/settings/imap"),
  updateImapSettings: (p: Record<string, unknown>) => request<ImapSettings>("PUT", "/settings/imap", p),
  testImapSettings: () => request<{ detail: string }>("POST", "/settings/imap/test"),

  // dashboard aggregate
  getDashboard: () => request<DashboardData>("GET", "/dashboard"),
  getAtRisk: () => request<AtRiskUser[]>("GET", "/dashboard/at-risk"),
  getChampions: () => request<Champion[]>("GET", "/dashboard/champions"),
  getRisk: () => request<RiskOut>("GET", "/dashboard/risk"),
  getGeo: () => request<GeoPoint[]>("GET", "/dashboard/geo"),
  getAttackSurface: () => request<AttackSurface>("GET", "/dashboard/attack-surface"),
  getBenchmark: () => request<Benchmark>("GET", "/dashboard/benchmark"),
  getBenchmarkSettings: () => request<BenchmarkSettings>("GET", "/settings/benchmark"),
  updateBenchmarkSettings: (p: Record<string, unknown>) => request<BenchmarkSettings>("PUT", "/settings/benchmark", p),
  getTimeline: () => request<TimelinePoint[]>("GET", "/dashboard/timeline"),

  // AI template generator (optional; requires VOLTPHISH_AI_API_KEY on the server)
  aiGenerateTemplate: (scenario: string, difficulty: string) =>
    request<AiTemplate>("POST", "/templates/ai-generate", { scenario, difficulty }),

  // landing pages
  listPages: () => request<PageSummary[]>("GET", "/pages"),
  getPage: (id: number) => request<LandingPage>("GET", `/pages/${id}`),
  createPage: (p: Record<string, unknown>) => request<LandingPage>("POST", "/pages", p),
  updatePage: (id: number, p: Record<string, unknown>) =>
    request<LandingPage>("PUT", `/pages/${id}`, p),
  deletePage: (id: number) => request<{ detail: string }>("DELETE", `/pages/${id}`),

  // test email
  sendTestEmail: (p: Record<string, unknown>) =>
    request<{ detail: string }>("POST", "/test/email", p),

  // webhooks (admin)
  checkDeliverability: (domain: string, selector: string | null) =>
    request<DeliverabilityResult>("POST", "/deliverability/check", { domain, selector }),
  generateAllowlist: (p: { domains: string[]; ips: string[]; urls: string[] }) =>
    request<AllowlistResult>("POST", "/deliverability/allowlist", p),

  listWebhooks: () => request<Webhook[]>("GET", "/webhooks"),
  createWebhook: (w: Record<string, unknown>) => request<Webhook>("POST", "/webhooks", w),
  updateWebhook: (id: number, w: Record<string, unknown>) => request<Webhook>("PUT", `/webhooks/${id}`, w),
  testWebhook: (id: number) => request<{ detail: string }>("POST", `/webhooks/${id}/test`),
  deleteWebhook: (id: number) => request<{ detail: string }>("DELETE", `/webhooks/${id}`),

  // API keys
  listApiKeys: () => request<ApiKey[]>("GET", "/apikeys"),
  createApiKey: (name: string) => request<ApiKeyCreated>("POST", "/apikeys", { name }),
  revokeApiKey: (id: number) => request<{ detail: string }>("DELETE", `/apikeys/${id}`),

  // campaigns
  listCampaigns: () => request<Campaign[]>("GET", "/campaigns"),
  getCampaign: (id: number) => request<CampaignDetail>("GET", `/campaigns/${id}`),
  createCampaign: (c: Record<string, unknown>) => request<Campaign>("POST", "/campaigns", c),
  previewRecipients: (p: { group_ids: number[]; exclude_group_ids: number[] }) =>
    request<{ count: number; unique: number; excluded: number; duplicates: number }>(
      "POST", "/campaigns/preview-recipients", p,
    ),
  launchCampaign: (id: number, body: { authorized: boolean; authorization_ref?: string }) =>
    request<CampaignDetail>("POST", `/campaigns/${id}/launch`, body),
  campaignEvents: (id: number) => request<EventItem[]>("GET", `/campaigns/${id}/events`),
  deleteCampaign: (id: number) => request<{ detail: string }>("DELETE", `/campaigns/${id}`),
  saveCampaignGroup: (id: number, p: { name: string; outcome: string }) =>
    request<{ group_id: number; name: string; added: number }>("POST", `/campaigns/${id}/save-group`, p),

  // people (cross-campaign risk view)
  listPeople: () => request<Person[]>("GET", "/people"),

  // public link (Cloudflare Tunnel) status
  getTunnel: () => request<{ configured: boolean; url: string | null; managed: boolean }>("GET", "/tunnel"),
};
