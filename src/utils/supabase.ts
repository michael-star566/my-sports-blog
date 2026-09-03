import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://wulgkgtqxkquzugjcmwv.supabase.co';
const supabaseAnonKey = 'sb_publishable_dlPyK2k9xkKDWPSQ1g3yUw_0lxhvixQ';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);