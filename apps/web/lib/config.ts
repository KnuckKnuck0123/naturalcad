export type PublicConfig = {
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
};

export const publicConfig: PublicConfig = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8010",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "https://your-project.supabase.co",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "your-public-anon-key",
};
