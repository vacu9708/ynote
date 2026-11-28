// Writes src/emoji-data.js, the emoji the picker offers, from the
// unicode-emoji-json package: by group, each with its name to search by.
// Only emoji up to version 14.0, which Ubuntu 22.04's Noto Color Emoji
// draws. Run after updating the package: node make-emoji.mjs
import {readFileSync, writeFileSync} from 'node:fs';

const groups = JSON.parse(readFileSync('node_modules/unicode-emoji-json/data-by-group.json', 'utf8'));
const out = groups.map(g => [g.name, g.emojis
  .filter(e => parseFloat(e.emoji_version) <= 14.0)
  .map(e => [e.emoji, e.name])]);
writeFileSync('src/emoji-data.js',
  '// Made by make-emoji.mjs from unicode-emoji-json: [group, [[emoji, name], ...]].\n' +
  'export const EMOJI = ' + JSON.stringify(out) + ';\n');
