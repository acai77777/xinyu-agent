import { readFileSync } from 'node:fs';
import ts from '../app/node_modules/typescript/lib/typescript.js';

const sourcePath = new URL('../app/app/chat/[id].tsx', import.meta.url);
const sourceText = readFileSync(sourcePath, 'utf8');
const sourceFile = ts.createSourceFile(
  sourcePath.pathname,
  sourceText,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);

function tagName(node) {
  return node.tagName?.getText(sourceFile);
}

function hasButtonRole(node) {
  return node.attributes?.properties.some((attribute) => (
    ts.isJsxAttribute(attribute)
    && attribute.name.getText(sourceFile) === 'accessibilityRole'
    && attribute.initializer?.getText(sourceFile) === '"button"'
  ));
}

function containsInteractiveDescendant(node) {
  let found = false;
  node.forEachChild((child) => {
    if (
      (ts.isJsxOpeningElement(child) || ts.isJsxSelfClosingElement(child))
      && ['TouchableOpacity', 'Pressable'].includes(tagName(child))
    ) {
      found = true;
    }
    if (!found) containsInteractiveDescendant(child) && (found = true);
  });
  return found;
}

let invalidOverlay = false;
function visit(node) {
  if (
    ts.isJsxElement(node)
    && tagName(node.openingElement) === 'Pressable'
    && hasButtonRole(node.openingElement)
    && containsInteractiveDescendant(node)
  ) {
    invalidOverlay = true;
  }
  node.forEachChild(visit);
}
visit(sourceFile);

if (invalidOverlay) {
  throw new Error('模型菜单遮罩不能以 button 角色包裹内部按钮');
}

console.log('model selector structure: ok');
