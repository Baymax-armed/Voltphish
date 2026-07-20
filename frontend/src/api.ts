// Thin fetch wrapper: same-origin cookies + CSRF header on mutations.
import type {
  AdminUser,
  ApiKey,
  ApiKeyCreated,
  AiTemplate,
  AtRiskUser,
  Champion,
  DeliverabilityResult,
  RiskOut,
  Attachment,
  Auth,
  Campaign,
  CampaignDetail,
  DashboardData,
  EventItem,
  Group,
  GroupSummary,
  LandingPage,
  PageSummary,
  Profile,
  RuntimeSettings,
  SmsProfile,
  Template,
  TemplateImportResult,
  TimelinePoint,
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
  login: (email: string, password: string) =>
    request<Auth>("POST", "/auth/login", { email, password }),
  logout: () => request<{ detail: string }>("POST", "/auth/logout"),
  me: () => request<Auth>("GET", "/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("POST", "/auth/change-password", { current_password, new_password }),

  // users (admin)
  listUsers: () => request<AdminUser[]>("GET", "/users"),
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

  // profiles
  listProfiles: () => request<Profile[]>("GET", "/profiles"),
  createProfile: (p: Record<string, unknown>) => request<Profile>("POST", "/profiles", p),
  updateProfile: (id: number, p: Record<string, unknown>) =>
    request<Profile>("PUT", `/profiles/${id}`, p),
  deleteProfile: (id: number) => request<{ detail: string }>("DELETE", `/profiles/${id}`),
  verifyProfile: (id: number) => request<{ detail: string }>("POST", `/profiles/${id}/verify`),

  // SMS profiles
  listSmsProfiles: () => request<SmsProfile[]>("GET", "/sms-profiles"),
  createSmsProfile: (p: Record<string, unknown>) => request<SmsProfile>("POST", "/sms-profiles", p),
  updateSmsProfile: (id: number, p: Record<string, unknown>) => request<SmsProfile>("PUT", `/sms-profiles/${id}`, p),
  deleteSmsProfile: (id: number) => request<{ detail: string }>("DELETE", `/sms-profiles/${id}`),
  verifySmsProfile: (id: number) => request<{ detail: string }>("POST", `/sms-profiles/${id}/verify`),
  testSmsProfile: (id: number, to: string, message: string) =>
    request<{ detail: string }>("POST", `/sms-profiles/${id}/test`, { to, message }),

  // runtime settings (for dev-mode banner)
  getSettings: () => request<RuntimeSettings>("GET", "/settings"),

  // dashboard aggregate
  getDashboard: () => request<DashboardData>("GET", "/dashboard"),
  getAtRisk: () => request<AtRiskUser[]>("GET", "/dashboard/at-risk"),
  getChampions: () => request<Champion[]>("GET", "/dashboard/champions"),
  getRisk: () => request<RiskOut>("GET", "/dashboard/risk"),
  getTimeline: () => request<TimelinePoint[]>("GET", "/dashboard/timeline"),

  // AI template generator (optional; requires PHISHSIM_AI_API_KEY on the server)
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
  launchCampaign: (id: number) => request<CampaignDetail>("POST", `/campaigns/${id}/launch`),
  campaignEvents: (id: number) => request<EventItem[]>("GET", `/campaigns/${id}/events`),
  deleteCampaign: (id: number) => request<{ detail: string }>("DELETE", `/campaigns/${id}`),
};
