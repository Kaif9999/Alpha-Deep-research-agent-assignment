export type Person = {
  id: number;  // Changed from string to number
  full_name: string;
  email: string;
  title: string;
  company_id: number;  // Changed from string to number
  created_at: string;
};

export type Progress = {
  percent: number;
  msg: string;
  iteration?: number;
  query?: string;
  found_fields?: string[];
};

export type ContextSnippet = {
  id: number;  // Changed from string to number
  entity_type: string;
  entity_id: number;  // Changed from string to number
  snippet_type: string;
  content: string;
  payload: Record<string, string>;
  source_urls: string[];
  created_at: string;
};

export type EnrichmentJob = {
  job_id: string;
  status: string;
};
