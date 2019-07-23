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

const nameToHSL = name => {
  let rng = xmur3(name);
  const h = rng() % 365;
  const s = rng() % 80 + 20;
  const l = rng() % 45 + 10;
  return `hsl(${ h }, ${ s }%, ${ l }%)`;
};


function logColorizer(logList) {
    for (let i = 0; i < logList.length; i++) {
        const log = logList[i];
        const speaker = log.querySelector(".speaker, .reply-to-speaker");
        if (speaker) {
            log.style.color = nameToHSL(speaker.innerText);
        }
    }
}

logColorizer(document.querySelectorAll('.log'));

logColorizer(document.querySelectorAll('.reply-to'));

const characters = document.querySelectorAll(".entity-character");

for (let i = 0; i < characters.length; i++) {
    const character = characters[i];
    if (character) {
        character.style.color = nameToHSL(character.innerText);
    }
}
