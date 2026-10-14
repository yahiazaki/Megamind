export type Citation = {
  n?: number;
  chunk_id: number;
  document_id: number;
  doc_title: string;
  section: string;
  page: number;
  book_page: number | null;
  snippet: string;
};

export type QuizItem = {
  id: number;
  type: "mcq" | "short";
  question: string;
  options: string[];
  topic: string;
  source: Partial<Citation>;
  answered: boolean;
  answer?: string;
  explanation?: string;
  user_answer?: string | null;
  score?: number | null;
  feedback?: string;
};

export type SessionSummary = {
  title?: string;
  summary?: string;
  topics?: string[];
  strengths?: string[];
  weaknesses?: string[];
  study_next?: { topic: string; why?: string; where?: string; book_page?: number }[];
  score?: string;
  whatsapp?: { status: string; error?: string };
};

export type ChatMessage = {
  id?: number;
  role: "user" | "assistant";
  content: string;
  kind: "text" | "quiz" | "quiz_result" | "summary" | "reminder";
  sources?: Citation[];
  items?: QuizItem[];
  data?: any;
  status?: string;
  error?: string;
  streaming?: boolean;
};

export type Session = {
  id: number;
  title: string;
  created_at: string;
  ended_at: string | null;
  summary: SessionSummary | null;
};

export type Doc = {
  id: number;
  title: string;
  subject: string;
  kind: string;
  status: string;
  error: string;
  pages: number;
  book_start_page: number | null;
  sort_order: number;
  chunks: number;
  file: string;
  created_at: string;
};

export type Job = {
  id: number;
  kind: string;
  document_id: number | null;
  status: string;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
};

export type Profile = {
  name?: string;
  headline?: string;
  location?: string;
  email?: string;
  phone?: string;
  show_phone_publicly?: boolean;
  links?: Record<string, string>;
  current?: { role?: string; company?: string; since?: string };
  summary?: string;
  experience?: { role: string; company: string; location?: string; start?: string; end?: string; highlights?: string[] }[];
  projects?: { name: string; stack?: string[]; highlights?: string[]; link?: string }[];
  skills?: Record<string, string[]>;
  certifications?: string[];
  education?: { degree: string; school: string; location?: string; start?: string; end?: string }[];
  languages?: string[];
  interests?: string[];
  [k: string]: any;
};

export type WorkTask = {
  id?: number;
  title: string;
  description: string;
  company: string;
  project: string;
  tags: string;
  impact: string;
  date: string | null;
  public: boolean;
};

export type Reminder = {
  id: number;
  title: string;
  notes: string;
  start: string;
  end: string | null;
  all_day: boolean;
  google: boolean;
};
