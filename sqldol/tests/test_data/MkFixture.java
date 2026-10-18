// Generates the synthetic Access fixtures in this folder (made-up rows):
//   tiny_jet4.mdb.gz    (Access 2000, Jet4):   java -cp "$CP:." MkFixture tiny_jet4.mdb V2000
//   tiny_ace.accdb.gz   (Access 2010, ACE):    java -cp "$CP:." MkFixture tiny_ace.accdb V2010
// then gzip -9 each. Jackcess 4.0.5 (Apache-2.0) + commons-lang3 3.12.0 + commons-logging 1.2,
// from Maven Central, on the classpath $CP; compile with: javac -cp "$CP" MkFixture.java

import com.healthmarketscience.jackcess.*;
import java.io.File;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public class MkFixture {
    public static void main(String[] args) throws Exception {
        Database db = new DatabaseBuilder(new File(args[0]))
            .setFileFormat(Database.FileFormat.valueOf(args[1])).create();
        Table t = new TableBuilder("Items")
            .addColumn(new ColumnBuilder("ID", DataType.LONG))
            .addColumn(new ColumnBuilder("Title", DataType.TEXT))
            .addColumn(new ColumnBuilder("Body", DataType.MEMO))
            .addColumn(new ColumnBuilder("Price", DataType.DOUBLE))
            .addColumn(new ColumnBuilder("Created", DataType.SHORT_DATE_TIME))
            .addColumn(new ColumnBuilder("Key", DataType.GUID))
            .addIndex(new IndexBuilder(IndexBuilder.PRIMARY_KEY_NAME).addColumns("ID").setPrimaryKey())
            .toTable(db);
        StringBuilder longBody = new StringBuilder();
        for (int i = 0; i < 300; i++) longBody.append("line ").append(i).append("; ");
        t.addRow(1, "alpha", "short memo", 1.5, LocalDateTime.of(2001, 2, 3, 4, 5, 6),
                 "{0B339502-3145-11D2-8D45-0080C6FD2CAA}");
        t.addRow(2, "béta", longBody.toString(), 2.25, LocalDateTime.of(2002, 3, 4, 0, 0, 0), null);
        t.addRow(3, "gamma", null, null, null, null);
        Table n = new TableBuilder("Numbers")
            .addColumn(new ColumnBuilder("ID", DataType.LONG))
            .addColumn(new ColumnBuilder("Amount", DataType.MONEY))
            .addColumn(new ColumnBuilder("Big", DataType.NUMERIC).setPrecision(18).setScale(0))
            .addColumn(new ColumnBuilder("Flag", DataType.BOOLEAN))
            .toTable(db);
        n.addRow(1, new BigDecimal("1234.5678"), new BigDecimal("123456789012345678"), true);
        n.addRow(2, new BigDecimal("0.0001"), new BigDecimal("-7"), false);
        n.addRow(3, null, null, false);
        Table c = new TableBuilder("Categories")
            .addColumn(new ColumnBuilder("ID", DataType.LONG))
            .addColumn(new ColumnBuilder("Name", DataType.TEXT))
            .toTable(db);
        c.addRow(10, "x");
        c.addRow(20, "y");
        db.close();
    }
}
