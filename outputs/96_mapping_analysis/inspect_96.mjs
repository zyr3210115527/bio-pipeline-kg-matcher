import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "/Users/zhouyiran/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_g28u5bj9tazm32_13f8/temp/drag/96例问题-数据-工具对应表(1).xlsx";
const outputDir = "/Users/zhouyiran/Documents/可选/bio-pipeline-kg-matcher/outputs/96_mapping_analysis";

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const overview = await workbook.inspect({
  kind: "workbook,sheet,table",
  include: "id,name,values,formulas",
  maxChars: 12000,
  tableMaxRows: 8,
  tableMaxCols: 12,
  tableMaxCellChars: 160,
});

await fs.writeFile(`${outputDir}/workbook_overview.ndjson`, overview.ndjson, "utf8");
const sheet1 = workbook.worksheets.getItem("Sheet1");
const used = sheet1.getUsedRange();
const rows = used.values;
await fs.writeFile(
  `${outputDir}/sheet1_rows.json`,
  JSON.stringify({ range: "A1:D97", rows }, null, 2) + "\n",
  "utf8",
);

const styles = await workbook.inspect({
  kind: "computedStyle",
  sheetId: "Sheet1",
  range: "A1:D12",
  maxChars: 6000,
});
await fs.writeFile(`${outputDir}/sheet1_styles.ndjson`, styles.ndjson, "utf8");

const preview = await workbook.render({
  sheetName: "Sheet1",
  range: "A1:D20",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(`${outputDir}/sheet1_preview.png`, new Uint8Array(await preview.arrayBuffer()));

console.log(JSON.stringify({
  overview: overview.ndjson.split("\n").filter(Boolean),
  rowCount: rows.length,
  firstRows: rows.slice(0, 5),
  lastRows: rows.slice(-3),
  styles: styles.ndjson.split("\n").filter(Boolean),
}, null, 2));
