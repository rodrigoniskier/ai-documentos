import {execFile} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';

import {config} from './config.js';
import type {DemoCapture, VideoPlan, VisualAssets} from './types.js';

const execFileAsync = promisify(execFile);
const boldFont = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';
const regularFont = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';

export async function audioDurationSeconds(audioPath: string): Promise<number> {
  const {stdout} = await execFileAsync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audioPath,
  ]);
  const value = Number(stdout.trim());
  if (!Number.isFinite(value) || value <= 0) return config.targetDurationSeconds - 4;
  return Math.max(60, Math.min(170, value));
}

function assTime(seconds: number): string {
  const safe = Math.max(0, seconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = (safe % 60).toFixed(2).padStart(5, '0');
  return `${hours}:${String(minutes).padStart(2, '0')}:${secs}`;
}

function assText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/\{/g, '\\{').replace(/\}/g, '\\}').replace(/\r?\n/g, '\\N');
}

function ffmpegFilterPath(value: string): string {
  return value.replace(/\\/g, '/').replace(/:/g, '\\:').replace(/'/g, "'\\''");
}

function wrapText(value: string, maxCharacters = 31): string {
  const words = value.replace(/\s+/g, ' ').trim().split(' ');
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > maxCharacters && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines.slice(0, 4).join('\n');
}

async function textFile(jobDir: string, name: string, value: string): Promise<string> {
  const destination = path.join(jobDir, name);
  await fs.writeFile(destination, value, 'utf8');
  return destination;
}

async function renderStillSegment(
  source: string,
  output: string,
  duration: number,
  headlineFile: string,
  eyebrow: string,
  darkOverlay = 0.52,
): Promise<void> {
  const frames = Math.ceil(duration * 30);
  const fadeOut = Math.max(0, duration - 0.38).toFixed(2);
  const filter = [
    'scale=1920:1080:force_original_aspect_ratio=increase',
    'crop=1920:1080',
    `zoompan=z='min(zoom+0.00032,1.095)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1920x1080:fps=30`,
    `drawbox=x=0:y=0:w=1920:h=1080:color=0x071c3b@${darkOverlay}:t=fill`,
    'drawbox=x=80:y=76:w=620:h=58:color=0xFFD21F@1:t=fill',
    `drawtext=fontfile=${boldFont}:text='${eyebrow}':fontcolor=0x071c3b:fontsize=27:x=105:y=91`,
    `drawtext=fontfile=${boldFont}:textfile='${ffmpegFilterPath(headlineFile)}':fontcolor=white:fontsize=72:line_spacing=18:x=88:y=(h-text_h)/2:shadowcolor=black@0.75:shadowx=4:shadowy=4`,
    `fade=t=in:st=0:d=.38,fade=t=out:st=${fadeOut}:d=.38`,
    'format=yuv420p',
  ].join(',');
  await execFileAsync('ffmpeg', [
    '-y', '-loop', '1', '-i', source, '-t', duration.toFixed(3), '-vf', filter,
    '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', output,
  ], {maxBuffer: 40 * 1024 * 1024});
}

async function renderSplitStillSegment(
  appShot: string,
  presenter: string,
  output: string,
  duration: number,
  headlineFile: string,
): Promise<void> {
  const fadeOut = Math.max(0, duration - 0.38).toFixed(2);
  const filter = [
    '[0:v]scale=1920:720:force_original_aspect_ratio=increase,crop=1920:720,setsar=1[top]',
    '[1:v]scale=1920:360:force_original_aspect_ratio=increase,crop=1920:360,setsar=1[bottom]',
    `color=c=0x071c3b:s=1920x1080:d=${duration}[base]`,
    '[base][top]overlay=0:0[tmp]',
    '[tmp][bottom]overlay=0:720[stack]',
    '[stack]drawbox=x=0:y=708:w=1920:h=12:color=0xFFD21F@1:t=fill,' +
      'drawbox=x=0:y=720:w=1920:h=360:color=0x071c3b@0.18:t=fill,' +
      `drawtext=fontfile=${boldFont}:text='APRESENTADORA VIRTUAL':fontcolor=0x071c3b:fontsize=24:x=80:y=760:box=1:boxcolor=0xFFD21F@1:boxborderw=14,` +
      `drawtext=fontfile=${boldFont}:textfile='${ffmpegFilterPath(headlineFile)}':fontcolor=white:fontsize=48:line_spacing=12:x=650:y=800:shadowcolor=black@0.75:shadowx=3:shadowy=3,` +
      `fade=t=in:st=0:d=.38,fade=t=out:st=${fadeOut}:d=.38,format=yuv420p[v]`,
  ].join(';');
  await execFileAsync('ffmpeg', [
    '-y', '-loop', '1', '-i', appShot, '-loop', '1', '-i', presenter, '-t', duration.toFixed(3),
    '-filter_complex', filter, '-map', '[v]', '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', output,
  ], {maxBuffer: 40 * 1024 * 1024});
}

async function renderDemoSegment(
  demoVideo: string,
  presenter: string,
  output: string,
  duration: number,
): Promise<void> {
  const fadeOut = Math.max(0, duration - 0.38).toFixed(2);
  const filter = [
    '[0:v]setpts=PTS-STARTPTS,scale=1920:720:force_original_aspect_ratio=decrease,pad=1920:720:(ow-iw)/2:(oh-ih)/2:0xF6F8FC,setsar=1[top]',
    '[1:v]scale=1920:360:force_original_aspect_ratio=increase,crop=1920:360,setsar=1[bottom]',
    `color=c=0x071c3b:s=1920x1080:d=${duration}[base]`,
    '[base][top]overlay=0:0[tmp]',
    '[tmp][bottom]overlay=0:720[stack]',
    '[stack]drawbox=x=0:y=708:w=1920:h=12:color=0xFFD21F@1:t=fill,' +
      'drawbox=x=0:y=720:w=1920:h=360:color=0x071c3b@0.22:t=fill,' +
      `drawtext=fontfile=${boldFont}:text='DEMONSTRAÇÃO REAL':fontcolor=0x071c3b:fontsize=24:x=80:y=760:box=1:boxcolor=0xFFD21F@1:boxborderw=14,` +
      `drawtext=fontfile=${regularFont}:text='A aplicação é real. A apresentadora é virtual.':fontcolor=white:fontsize=30:x=80:y=842,` +
      `drawtext=fontfile=${boldFont}:text='A autoria permanece com o professor. O sistema organiza o trabalho mecânico.':fontcolor=white:fontsize=38:x=650:y=810:shadowcolor=black@0.75:shadowx=3:shadowy=3,` +
      `fade=t=in:st=0:d=.38,fade=t=out:st=${fadeOut}:d=.38,format=yuv420p[v]`,
  ].join(';');
  await execFileAsync('ffmpeg', [
    '-y', '-stream_loop', '-1', '-i', demoVideo, '-loop', '1', '-i', presenter, '-t', duration.toFixed(3),
    '-filter_complex', filter, '-map', '[v]', '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', output,
  ], {maxBuffer: 60 * 1024 * 1024});
}

async function renderCtaSegment(
  source: string,
  output: string,
  duration: number,
  ctaFile: string,
): Promise<void> {
  const frames = Math.ceil(duration * 30);
  const fadeOut = Math.max(0, duration - 0.38).toFixed(2);
  const filter = [
    'scale=1920:1080:force_original_aspect_ratio=increase',
    'crop=1920:1080',
    `zoompan=z='min(zoom+0.0002,1.045)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1920x1080:fps=30`,
    'drawbox=x=0:y=0:w=1920:h=1080:color=0x071c3b@0.42:t=fill',
    `drawtext=fontfile=${boldFont}:text='${config.channelName.toUpperCase()}':fontcolor=0xFFD21F:fontsize=42:x=(w-text_w)/2:y=190`,
    `drawtext=fontfile=${boldFont}:textfile='${ffmpegFilterPath(ctaFile)}':fontcolor=white:fontsize=68:line_spacing=18:x=(w-text_w)/2:y=360:shadowcolor=black@0.8:shadowx=4:shadowy=4`,
    'drawbox=x=610:y=700:w=700:h=112:color=0xFFD21F@1:t=fill',
    `drawtext=fontfile=${boldFont}:text='SOLICITE UM DIAGNÓSTICO':fontcolor=0x071c3b:fontsize=38:x=(w-text_w)/2:y=735`,
    `drawtext=fontfile=${regularFont}:text='Link e contato na descrição':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=865`,
    `fade=t=in:st=0:d=.38,fade=t=out:st=${fadeOut}:d=.38`,
    'format=yuv420p',
  ].join(',');
  await execFileAsync('ffmpeg', [
    '-y', '-loop', '1', '-i', source, '-t', duration.toFixed(3), '-vf', filter,
    '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', output,
  ], {maxBuffer: 40 * 1024 * 1024});
}

async function buildCaptions(jobDir: string, narration: string, duration: number): Promise<string> {
  const sentences = narration
    .replace(/\s+/g, ' ')
    .trim()
    .split(/(?<=[.!?])\s+/)
    .filter(Boolean);
  const totalCharacters = Math.max(1, sentences.reduce((sum, sentence) => sum + sentence.length, 0));
  const events: string[] = [];
  let cursor = 0.4;
  const usableDuration = Math.max(1, duration - 1.2);
  for (const sentence of sentences) {
    const allocated = usableDuration * (sentence.length / totalCharacters);
    const end = Math.min(duration - 0.3, cursor + Math.max(1.8, allocated));
    events.push(`Dialogue: 0,${assTime(cursor)},${assTime(end)},Subtitle,,0,0,0,,${assText(sentence)}`);
    cursor = end;
  }
  const assPath = path.join(jobDir, 'captions.ass');
  const ass = `[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Subtitle,DejaVu Sans,42,&H00FFFFFF,&H00FFFFFF,&H00101A2A,&H9A071C3B,0,0,0,0,100,100,0,0,3,14,1,2,110,110,42,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n${events.join('\n')}\n`;
  await fs.writeFile(assPath, ass, 'utf8');
  return assPath;
}

export async function renderVideo(
  jobDir: string,
  plan: VideoPlan,
  capture: DemoCapture,
  audioPath: string,
  musicPath: string,
  assets: VisualAssets,
): Promise<string> {
  const audioDuration = await audioDurationSeconds(audioPath);
  const totalDuration = Math.max(config.targetDurationSeconds, audioDuration + 3);
  const fixedDuration = 56;
  const demoDuration = Math.max(34, totalDuration - fixedDuration);
  const durations = [11, 10, 10, demoDuration, 15, 10];
  const segmentFiles = durations.map((_, index) => path.join(jobDir, `professional-${String(index + 1).padStart(2, '0')}.mp4`));

  const hookFile = await textFile(jobDir, 'hook.txt', wrapText(plan.hook, 32));
  const painFile = await textFile(jobDir, 'pain.txt', wrapText('Horas de leitura, formatação e conferência manual.', 32));
  const presenterFile = await textFile(jobDir, 'presenter-line.txt', wrapText(plan.presenterLine, 48));
  const closingFile = await textFile(jobDir, 'closing.txt', wrapText(plan.closing, 35));
  const ctaFile = await textFile(jobDir, 'cta.txt', wrapText(plan.cta, 38));

  await renderStillSegment(assets.painDesk, segmentFiles[0]!, durations[0]!, hookFile, 'O FARDO DO MÉTODO TRADICIONAL');
  await renderStillSegment(assets.painHands, segmentFiles[1]!, durations[1]!, painFile, 'TEMPO CONSUMIDO EM TAREFAS MECÂNICAS', 0.58);
  await renderSplitStillSegment(path.join(jobDir, capture.shots.inicio), assets.presenter, segmentFiles[2]!, durations[2]!, presenterFile);
  await renderDemoSegment(path.join(jobDir, capture.video), assets.presenter, segmentFiles[3]!, durations[3]!);
  await renderStillSegment(assets.relief, segmentFiles[4]!, durations[4]!, closingFile, 'A EFICIÊNCIA AUTOMATIZADA', 0.45);
  await renderCtaSegment(assets.ctaBackground, segmentFiles[5]!, durations[5]!, ctaFile);

  const concatList = path.join(jobDir, 'professional-scenes.txt');
  await fs.writeFile(concatList, segmentFiles.map((file) => `file '${file.replace(/'/g, "'\\''")}'`).join('\n'));
  const visuals = path.join(jobDir, 'professional-visuals.mp4');
  await execFileAsync('ffmpeg', [
    '-y', '-f', 'concat', '-safe', '0', '-i', concatList,
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-an', visuals,
  ], {maxBuffer: 60 * 1024 * 1024});

  const captionsPath = await buildCaptions(jobDir, plan.narration, audioDuration);
  const output = path.join(jobDir, 'video-final.mp4');
  const musicFadeOut = Math.max(0, totalDuration - 4).toFixed(2);
  const filter = [
    `[0:v]ass='${ffmpegFilterPath(captionsPath)}'[v]`,
    '[1:a]volume=1.08,apad=pad_dur=3[voice]',
    `[2:a]volume=0.24,afade=t=in:st=0:d=2.2,afade=t=out:st=${musicFadeOut}:d=4[music]`,
    '[music][voice]sidechaincompress=threshold=0.018:ratio=9:attack=18:release=360[ducked]',
    '[voice][ducked]amix=inputs=2:duration=longest:dropout_transition=2,alimiter=limit=0.95[a]',
  ].join(';');
  await execFileAsync('ffmpeg', [
    '-y', '-i', visuals, '-i', audioPath, '-stream_loop', '-1', '-i', musicPath,
    '-filter_complex', filter, '-map', '[v]', '-map', '[a]', '-t', totalDuration.toFixed(3),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '224k', '-movflags', '+faststart', output,
  ], {maxBuffer: 80 * 1024 * 1024});
  return output;
}

export async function renderThumbnail(
  jobDir: string,
  plan: VideoPlan,
  capture: DemoCapture,
  assets: VisualAssets,
): Promise<string> {
  const titleFile = path.join(jobDir, 'thumbnail-title.txt');
  await fs.writeFile(titleFile, wrapText(plan.hook || plan.title, 29));
  const source = path.join(jobDir, capture.shots.formulario || capture.shots.inicio);
  const output = path.join(jobDir, 'thumbnail.jpg');
  const filter = [
    '[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720[app]',
    '[1:v]scale=470:720:force_original_aspect_ratio=increase,crop=470:720[presenter]',
    '[app]drawbox=x=0:y=0:w=1280:h=720:color=0x071c3b@0.54:t=fill[base]',
    '[base][presenter]overlay=810:0[mix]',
    '[mix]drawbox=x=48:y=45:w=620:h=58:color=0xFFD21F@1:t=fill,' +
      `drawtext=fontfile=${boldFont}:text='AI LAB RODRIGO NISKIER':fontcolor=0x071c3b:fontsize=27:x=72:y=59,` +
      `drawtext=fontfile=${boldFont}:textfile='${ffmpegFilterPath(titleFile)}':fontcolor=white:fontsize=58:line_spacing=14:x=58:y=(h-text_h)/2:shadowcolor=black@0.8:shadowx=4:shadowy=4,` +
      `drawtext=fontfile=${boldFont}:text='PROCESSOS INTELIGENTES':fontcolor=0xFFD21F:fontsize=28:x=58:y=h-70[v]`,
  ].join(';');
  await execFileAsync('ffmpeg', [
    '-y', '-i', source, '-i', assets.presenter, '-filter_complex', filter, '-map', '[v]', '-frames:v', '1', '-q:v', '2', output,
  ], {maxBuffer: 30 * 1024 * 1024});
  return output;
}
