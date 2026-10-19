// Check media lifecycle races with mocked media elements, without browser playback claims.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup(getSource, isAllowed = () => true) {
  const videos = [], revoked = [], warnings = [];
  const playResults = [];
  const context = vm.createContext({
    window: {}, Blob,
    console: {warn: (...args) => warnings.push(args)},
    URL: {createObjectURL: () => 'blob:preview', revokeObjectURL: url => revoked.push(url)},
    IntersectionObserver: class {
      constructor(callback) { this.callback = callback; }
      observe() {}
      unobserve() {}
    },
    document: {createElement() {
      const video = {
        paused: true, classList: {add() {}},
        setAttribute() {}, removeAttribute() {}, load() {},
        remove() { this.removed = true; },
        pause() { this.paused = true; },
        play() { this.paused = false; return playResults.shift() || Promise.resolve(); },
      };
      videos.push(video);
      return video;
    }},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'local_previews.js'), 'utf8'), context);
  const player = new context.window.LocalCardPreview(getSource, isAllowed);
  return {player, videos, playResults, revoked, warnings};
}

const card = () => ({isConnected: true});
const container = () => ({appendChild() {}});
const status = () => ({hidden: true, textContent: ''});
const source = id => ({url: `media/${id}.mp4`, kind: 'video'});

(async () => {
  const a = card(), b = card();
  const normal = setup(source);
  assert.equal(normal.videos.length, 0);
  await normal.player.play(a, container(), status(), 'a');
  assert.equal(normal.videos[0].muted, true);
  assert.equal(normal.videos[0].loop, true);
  normal.player.stopFor(b);
  assert.equal(normal.videos[0].paused, false);
  normal.player.stopFor(a);
  assert.equal(normal.videos[0].paused, true);
  assert.equal(normal.videos[0].removed, true);

  let resolveSource;
  const delayed = setup(id => id === 'a' ? new Promise(resolve => {resolveSource = resolve;}) : source(id));
  const first = delayed.player.play(a, container(), status(), 'a');
  await delayed.player.play(b, container(), status(), 'b');
  resolveSource(source('a'));
  await first;
  assert.equal(delayed.videos.length, 1);
  assert.equal(delayed.player.card, b);

  let resolvePlay;
  const pending = setup(source);
  pending.playResults.push(new Promise(resolve => {resolvePlay = resolve;}));
  const old = pending.player.play(a, container(), status(), 'a');
  await Promise.resolve();
  await pending.player.play(b, container(), status(), 'b');
  resolvePlay();
  await old;
  assert.equal(pending.videos[0].paused, true);
  assert.equal(pending.videos[1].paused, false);
  const activeContainer = pending.player.container;
  pending.player.observer.callback([{target: activeContainer, isIntersecting: false}]);
  assert.equal(pending.videos[1].paused, true);

  const image = setup(() => ({url: 'media/image.png', kind: 'image'}));
  await image.player.play(a, container(), status(), 'image');
  assert.equal(image.videos.length, 0);
  const blocked = setup(source, () => false);
  await blocked.player.play(a, container(), status(), 'a');
  assert.equal(blocked.videos.length, 0);

  const blob = setup(() => ({blob: new Blob(['fixture'])}));
  await blob.player.play(a, container(), status(), 'a');
  blob.player.stop();
  assert.deepEqual(blob.revoked, ['blob:preview']);

  const denied = setup(source);
  const message = status();
  const error = new Error('Autoplay denied'); error.name = 'NotAllowedError';
  denied.playResults.push(Promise.reject(error));
  await denied.player.play(a, container(), message, 'a');
  assert.equal(message.hidden, false);
  assert.match(message.textContent, /自动播放/);
  assert.equal(denied.player.video, null);
  assert.equal(denied.warnings.length, 1);
  console.log('6 card preview lifecycle scenarios passed (media elements mocked).');
})().catch(error => { console.error(error); process.exitCode = 1; });
