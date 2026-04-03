export class MobjectRegistry {
  constructor() {
    this._registry = new Map();
  }

  clear() {
    this._registry.clear();
  }

  get(id) {
    return this._registry.get(id);
  }

  set(id, mobject) {
    this._registry.set(id, mobject);
    return mobject;
  }

  delete(id) {
    return this._registry.delete(id);
  }

  rebind(sourceId, targetId) {
    if (sourceId === targetId) {
      return this._registry.get(sourceId) || null;
    }

    const mob = this._registry.get(sourceId);
    if (!mob) {
      console.warn(`Cannot rebind missing source id: ${sourceId}`);
      return null;
    }

    this._registry.delete(sourceId);
    this._registry.set(targetId, mob);
    return mob;
  }
}
