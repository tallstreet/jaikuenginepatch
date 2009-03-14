
#png('./prof_db.png', width=800, height=400)

library(reshape)

#par(mar=c(3, 12, 3, 3))

all_data <- read.table(INFILE, 
                       header=FALSE, 
                       sep=",", 
                       col.names=c('label', 'kind','call','time_ms'))
all_melted <- melt(all_data)

all_casted_counts <- as.matrix(cast(all_melted, label ~ kind, length))

# default columns, ordered from saddest to happiest
base_values <- data.frame(
                         write=0,
                         read=0,
                         threadlocal_cached_read=0,
                         threadlocal_cache_miss=0,
                         threadlocal_cache_hit=0
                         )

rows = rownames(all_casted_counts)
cols = colnames(all_casted_counts)


png(OUTFILE, width=1200, height=150 * length(rows), type=OUTTYPE)
par(mfrow=c(length(rows), 1), mar=c(3, 12, 3, 3))

#bar_colors <- heat.colors(5)
bar_colors <- rainbow(5)

for (i in 1:length(rows)) {
  bv <- base_values
  for (j in 1:length(cols)) {
    bv[cols[j]] = all_casted_counts[i,j]
  }
  bv_m <- as.matrix(bv)

  barplot(bv_m,
          horiz=TRUE, 
          beside=TRUE, 
          col=bar_colors, 
          las=2,
          xlim=c(0, 500),
          width=c(1),
          main=rows[i]
          )
}
