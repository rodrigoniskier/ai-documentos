export type Shot = 'inicio' | 'periodo' | 'componente' | 'tipo' | 'formulario';

export interface VideoScene {
  caption: string;
  shot: Shot;
}

export interface VideoPlan {
  hook: string;
  narration: string;
  title: string;
  description: string;
  tags: string[];
  cta: string;
  scenes: VideoScene[];
}

export interface GenerationResult {
  id: string;
  videoPath: string;
  plan: VideoPlan;
  youtubeVideoId?: string;
  youtubeUrl?: string;
}
