import path from "path";

/** Validate that a resolved path is inside the builds data directory. */
export function isInsideBuildDir(dirPath: string): boolean {
  const expectedBase = path.resolve(process.cwd(), "data", "builds") + path.sep;
  return path.resolve(dirPath).startsWith(expectedBase);
}
