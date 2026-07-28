import {execFile} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import {promisify} from 'node:util';

import type {Shot, VideoPlan} from './types.js';

const execFileAsync = promisify(execFile);

async function audioDurationSeconds(audioPath: string): Promise<number> {
  const {stdout} = await execFileAsync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audioPath,
  ]);
  const value = Number(stdout.trim());
  if (!Number.isFinite(value) || value <= 0) return 40;
  return Math.max(15, Math.min(60, value));
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

export async function renderVideo(jobDir: string, plan: VideoPlan, shots: Record<Shot, string>, audioPath: string): Promise<string> {
  const audioDuration = await audioDurationSeconds(audioPath);
  const totalDuration = audioDuration + 1.2;
  const sceneDuration = totalDuration / plan.scenes.length;
  const sceneFiles: string[] = [];

  for (let index = 0; index < plan.scenes.length; index += 1) {
    const scene = plan.scenes[index];
    if (!scene) continue;
    const input = path.join(jobDir, shots[scene.shot]);
    const output = path.join(jobDir, `scene-${String(index + 1).padStart(2, '0')}.mp4`);
    const frames = Math.max(1, Math.ceil(sceneDuration * 30));
    const videoFilter = [
      'scale=1080:1920:force_original_aspect_ratio=increase',
      'crop=1080:1920',
      `zoompan=z='min(zoom+0.00055,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1080x1920:fps=30`,
      'format=yuv420p',
    ].join(',');
    await execFileAsync('ffmpeg', [
      '-y', '-loop', '1', '-i', input, '-t', sceneDuration.toFixed(3), '-vf', videoFilter,
      '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', output,
    ], {maxBuffer: 20 * 1024 * 1024});
    sceneFiles.push(output);
  }

  const concatList = path.join(jobDir, 'scenes.txt');
  await fs.writeFile(concatList, sceneFiles.map((file) => `file '${file.replace(/'/g, "'\\''")}'`).join('\n'));
  const visuals = path.join(jobDir, 'visuals.mp4');
  await execFileAsync('ffmpeg', [
    '-y', '-f', 'concat', '-safe', '0', '-i', concatList,
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-an', visuals,
  ], {maxBuffer: 20 * 1024 * 1024});

  const assPath = path.join(jobDir, 'captions.ass');
  const events: string[] = [];
  for (let index = 0; index < plan.scenes.length; index += 1) {
    const scene = plan.scenes[index];
    if (!scene) continue;
    const start = index * sceneDuration;
    const end = Math.min(totalDuration, (index + 1) * sceneDuration);
    events.push(`Dialogue: 0,${assTime(start)},${assTime(end)},Brand,,0,0,0,,RN PROCESSOS INTELIGENTES`);
    events.push(`Dialogue: 0,${assTime(start)},${assTime(end)},Caption,,0,0,0,,${assText(scene.caption)}`);
  }
  events.push(`Dialogue: 1,${assTime(Math.max(0, totalDuration - 3.2))},${assTime(totalDuration)},CTA,,0,0,0,,${assText(plan.cta)}`);
  const ass = `[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Brand,DejaVu Sans,27,&H00071C3B,&H00071C3B,&H00FFD21F,&H00FFD21F,-1,0,0,0,100,100,1,0,3,10,0,7,45,45,45,1\nStyle: Caption,DejaVu Sans,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90071C3B,-1,0,0,0,100,100,0,0,3,18,1,2,70,70,185,1\nStyle: CTA,DejaVu Sans,64,&H00FFFFFF,&H00FFFFFF,&H000B4EA2,&HC0071C3B,-1,0,0,0,100,100,0,0,3,22,2,5,75,75,0,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n${events.join('\n')}\n`;
  await fs.writeFile(assPath, ass);

  const output = path.join(jobDir, 'video-final.mp4');
  await execFileAsync('ffmpeg', [
    '-y', '-i', visuals, '-i', audioPath,
    '-filter_complex', `[0:v]ass='${ffmpegFilterPath(assPath)}'[v];[1:a]apad=pad_dur=1.2[a]`,
    '-map', '[v]', '-map', '[a]', '-t', totalDuration.toFixed(3),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', output,
  ], {maxBuffer: 30 * 1024 * 1024});
  return output;
}
