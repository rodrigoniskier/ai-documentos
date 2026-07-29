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
  closing: string;
  presenterLine: string;
  scenes: VideoScene[];
}

export interface DemoCapture {
  shots: Record<Shot, string>;
  video: string;
}

export interface VisualAssets {
  painDesk: string;
  painHands: string;
  presenter: string;
  relief: string;
  ctaBackground: string;
}

export interface GenerationResult {
  id: string;
  createdAt: string;
  videoPath: string;
  thumbnailPath: string;
  publicationTextPath: string;
  plan: VideoPlan;
}
