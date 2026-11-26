export interface Course {
  year: number;
  term: '1' | '2' | 'summer' | 'winter';
  course_code: string | null;
  name: string;
  category: string;
  credits: number;
  grade: string | null;
  is_retake: boolean;
}

export interface ParseWarning {
  row: number;
  message: string;
}

export interface TranscriptParseResponse {
  admission_year: number | null;
  courses: Course[];
  parse_warnings: ParseWarning[];
}
