import fs from 'node:fs/promises';

const TAU = Math.PI * 2;

function noteFrequency(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function noise(index: number): number {
  const value = Math.sin((index + 1) * 12.9898) * 43758.5453;
  return (value - Math.floor(value)) * 2 - 1;
}

function softClip(value: number): number {
  return Math.tanh(value * 1.18) * 0.86;
}

function writeWavHeader(buffer: Buffer, frames: number, sampleRate: number): void {
  const channels = 2;
  const bitsPerSample = 16;
  const dataSize = frames * channels * (bitsPerSample / 8);
  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write('WAVE', 8);
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(channels, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * channels * (bitsPerSample / 8), 28);
  buffer.writeUInt16LE(channels * (bitsPerSample / 8), 32);
  buffer.writeUInt16LE(bitsPerSample, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataSize, 40);
}

export async function generateBackgroundMusic(destination: string, durationSeconds: number): Promise<void> {
  const sampleRate = 44100;
  const duration = Math.max(45, Math.min(180, durationSeconds));
  const frames = Math.ceil(duration * sampleRate);
  const output = Buffer.allocUnsafe(44 + frames * 4);
  writeWavHeader(output, frames, sampleRate);

  const bpm = 118;
  const beatDuration = 60 / bpm;
  const progression = [
    [50, 54, 57],
    [45, 49, 52],
    [47, 50, 54],
    [43, 47, 50],
  ];
  const arpPattern = [0, 1, 2, 1, 0, 1, 2, 1];
  let previousNoise = 0;

  for (let frame = 0; frame < frames; frame += 1) {
    const t = frame / sampleRate;
    const beat = t / beatDuration;
    const beatInBar = beat % 4;
    const chordIndex = Math.floor(beat / 4) % progression.length;
    const chord = progression[chordIndex] || progression[0]!;
    const root = chord[0]!;

    const intro = Math.min(1, t / 3.2);
    const outro = Math.min(1, Math.max(0, (duration - t) / 4.2));
    const masterEnvelope = intro * outro;
    const kickPhase = (t % beatDuration) / beatDuration;
    const sidechain = 0.62 + 0.38 * Math.min(1, kickPhase * 5.5);

    let padLeft = 0;
    let padRight = 0;
    for (let noteIndex = 0; noteIndex < chord.length; noteIndex += 1) {
      const midi = chord[noteIndex]! + 12;
      const frequency = noteFrequency(midi);
      const phase = noteIndex * 0.72;
      const tone = Math.sin(TAU * frequency * t + phase) + 0.24 * Math.sin(TAU * frequency * 2 * t + phase * 0.7);
      padLeft += tone * (noteIndex === 2 ? 0.78 : 1);
      padRight += tone * (noteIndex === 0 ? 0.8 : 1);
    }
    padLeft *= 0.038 * sidechain;
    padRight *= 0.038 * sidechain;

    const eighthDuration = beatDuration / 2;
    const eighth = Math.floor(t / eighthDuration);
    const arpAge = t - eighth * eighthDuration;
    const arpNote = chord[arpPattern[eighth % arpPattern.length] || 0]! + 24;
    const arpFrequency = noteFrequency(arpNote);
    const arpEnvelope = Math.exp(-arpAge * 11.5);
    const arpTone = (
      Math.sin(TAU * arpFrequency * t) +
      0.42 * Math.sin(TAU * arpFrequency * 2 * t) +
      0.18 * Math.sin(TAU * arpFrequency * 3 * t)
    ) * arpEnvelope * 0.075;
    const arpPan = eighth % 2 === 0 ? 0.78 : 1.18;

    const bassAge = t - Math.floor(t / beatDuration) * beatDuration;
    const bassEnvelope = Math.exp(-bassAge * 4.8);
    const bassFrequency = noteFrequency(root - 12);
    const bass = (Math.sin(TAU * bassFrequency * t) + 0.22 * Math.sin(TAU * bassFrequency * 2 * t)) * bassEnvelope * 0.15;

    const kickAge = t - Math.floor(t / beatDuration) * beatDuration;
    const kickFrequency = 48 + 82 * Math.exp(-kickAge * 28);
    const kick = Math.sin(TAU * kickFrequency * kickAge) * Math.exp(-kickAge * 17) * 0.34;

    const nearestBackbeat = Math.min(Math.abs(beatInBar - 1), Math.abs(beatInBar - 3));
    const snareAge = nearestBackbeat * beatDuration;
    const rawNoise = noise(frame);
    const highNoise = rawNoise - previousNoise * 0.82;
    previousNoise = rawNoise;
    const snare = nearestBackbeat < 0.28 ? highNoise * Math.exp(-snareAge * 23) * 0.12 : 0;

    const hatAge = t - Math.floor(t / eighthDuration) * eighthDuration;
    const hat = highNoise * Math.exp(-hatAge * 58) * 0.036;

    const lift = 0.012 * Math.sin(TAU * 0.125 * t) + 0.008 * Math.sin(TAU * 0.25 * t + 1.1);
    const left = softClip((padLeft + arpTone * arpPan + bass + kick + snare + hat + lift) * masterEnvelope);
    const right = softClip((padRight + arpTone * (2 - arpPan) + bass + kick + snare * 0.92 + hat * 1.08 - lift) * masterEnvelope);

    const offset = 44 + frame * 4;
    output.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(left * 32767))), offset);
    output.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round(right * 32767))), offset + 2);
  }

  await fs.writeFile(destination, output);
}
