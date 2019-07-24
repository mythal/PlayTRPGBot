let replyList = document.querySelectorAll('.reply-to-link');

function highlight() {
  let link = document.querySelector(this.getAttribute('href'));
  link.className = link.className.replace(' highlight', '');
  setTimeout(() => {
    link.className += ' highlight';
  }, 200);
}

for (let i = 0; i < replyList.length; i++) {
  replyList[i].addEventListener('click', highlight);
}

function xmur3(str) {
  let h = 1779033703 ^ str.length;
  for(let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = h << 13 | h >>> 19;
  }
  return function() {
    h = Math.imul(h ^ h >>> 16, 2246822507);
    h = Math.imul(h ^ h >>> 13, 3266489909);
    return (h ^= h >>> 16) >>> 0;
  }
}


const nameColorMap = {};


const nameToHSL = name => {
  if (nameColorMap[name]) {
    return nameColorMap[name];
  }
  let rng = xmur3(name);
  const h = rng() % 365;
  const s = rng() % 80 + 20;
  const l = rng() % 20 + rng() % 20 + rng() % 20;
  const color = `hsl(${ h }, ${ s }%, ${ l }%)`;
  nameColorMap[name] = color;
  return color;
};

function logColorizer() {
  const contents = document.querySelectorAll('.content');
  for (let i = 0; i < contents.length; i++) {
    const log = contents[i];
    const speaker = log.querySelector(".speaker");
    if (speaker) {
      log.style.color = nameToHSL(speaker.innerText);
    }
  }
}

logColorizer();


function characterColorizer() {
  const characters = document.querySelectorAll(".entity-character");

  for (let i = 0; i < characters.length; i++) {
    const character = characters[i];
    if (character) {
      character.style.color = nameToHSL(character.innerText);
    }
  }
}

characterColorizer();
