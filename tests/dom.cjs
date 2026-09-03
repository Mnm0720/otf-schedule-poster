// A minimal event/element adapter for unit tests; no browser or layout simulation.
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.value = ''; this.checked = false;
    this.hidden = false; this.disabled = false; this.style = {};
    this.classList = {toggle() {}};
  }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.append(child); return child; }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(key, value) { this[key] = value; }
  querySelectorAll() { return []; }
  focus() { this.focused = true; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  remove() {}
}
class Document {
  constructor() { this.elements = new Map(); this.body = new Element('body'); }
  createElement(tag) { return new Element(tag); }
  querySelectorAll() { return []; }
  getElementById(id) {
    if (!this.elements.has(id)) this.elements.set(id, new Element());
    return this.elements.get(id);
  }
}
function all(element) { return [element, ...element.children.filter(x => x instanceof Element).flatMap(all)]; }
function labelled(element, label) { return all(element).find(e => e['aria-label'] === label); }
module.exports = {Element, Document, all, labelled};
