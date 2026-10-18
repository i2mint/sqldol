// Generates sqldol/tests/test_data/tiny_jet4.mdb.gz: a synthetic Access 2000 (Jet4) file, made-up rows.
// Jackcess 4.0.5 (Apache-2.0) + commons-lang3 3.12.0 + commons-logging 1.2, from Maven Central:
//   javac -cp "$CP" MkFixture.java && java -cp "$CP:." MkFixture tiny_jet4.mdb && gzip -9 tiny_jet4.mdb

import com.healthmarketscience.jackcess.*;
import java.io.File;
import java.time.LocalDateTime;

public class MkFixture {
    public static void main(String[] args) throws Exception {
        Database db = new DatabaseBuilder(new File(args[0]))
            .setFileFormat(Database.FileFormat.V2000).create();
        Table t = new TableBuilder("Items")
            .addColumn(new ColumnBuilder("ID", DataType.LONG))
            .addColumn(new ColumnBuilder("Title", DataType.TEXT))
            .addColumn(new ColumnBuilder("Body", DataType.MEMO))
            .addColumn(new ColumnBuilder("Price", DataType.DOUBLE))
            .addColumn(new ColumnBuilder("Created", DataType.SHORT_DATE_TIME))
            .addIndex(new IndexBuilder(IndexBuilder.PRIMARY_KEY_NAME).addColumns("ID").setPrimaryKey())
            .toTable(db);
        StringBuilder longBody = new StringBuilder();
        for (int i = 0; i < 300; i++) longBody.append("line ").append(i).append("; ");
        t.addRow(1, "alpha", "short memo", 1.5, LocalDateTime.of(2001, 2, 3, 4, 5, 6));
        t.addRow(2, "béta", longBody.toString(), 2.25, LocalDateTime.of(2002, 3, 4, 0, 0, 0));
        t.addRow(3, "gamma", null, null, null);
        Table c = new TableBuilder("Categories")
            .addColumn(new ColumnBuilder("ID", DataType.LONG))
            .addColumn(new ColumnBuilder("Name", DataType.TEXT))
            .toTable(db);
        c.addRow(10, "x");
        c.addRow(20, "y");
        db.close();
    }
}
