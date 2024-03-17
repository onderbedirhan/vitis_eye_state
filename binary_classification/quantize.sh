vai_q_tensorflow quantize \
	--input_frozen_graph frozen_graph.pb \
	--input_nodes x \
	--input_shapes ?,150,150,1 \
	--output_nodes sequential/dense_2/Sigmoid \
	--input_fn input_fn.calib_input \
	--calib_iter 100 \
	--output_dir ./quantize_results \

