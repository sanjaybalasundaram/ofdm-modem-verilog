// Radix-2 decimation-in-time butterfly (combinational), Q1.15.
//   t = b * w            (complex multiply, rounded back to Q1.15)
//   x = (a + t) / 2      (rounded, saturated)
//   y = (a - t) / 2
// Dividing by 2 in every stage stops the values growing, so a 6-stage FFT
// never overflows (total scale = 1/64).
module butterfly_r2 (
    input  signed [15:0] ar, ai,      // input a
    input  signed [15:0] br, bi,      // input b
    input  signed [15:0] wr, wi,      // twiddle factor
    output signed [15:0] xr, xi,      // a + b*w (scaled)
    output signed [15:0] yr, yi       // a - b*w (scaled)
);
    // Full-precision products: 16 x 16 -> 32 bits, sum -> 33 bits
    wire signed [32:0] pr = br * wr - bi * wi;
    wire signed [32:0] pi = br * wi + bi * wr;

    // Round (add half an LSB) and drop 15 fraction bits -> 18-bit result
    wire signed [32:0] pr_rnd = pr + 33'sd16384;
    wire signed [32:0] pi_rnd = pi + 33'sd16384;
    wire signed [17:0] tr = pr_rnd[32:15];
    wire signed [17:0] ti = pi_rnd[32:15];

    // Add / subtract with rounding, then divide by 2
    wire signed [18:0] sr = ar + tr + 19'sd1;
    wire signed [18:0] si = ai + ti + 19'sd1;
    wire signed [18:0] dr = ar - tr + 19'sd1;
    wire signed [18:0] di = ai - ti + 19'sd1;

    function signed [15:0] sat16(input signed [17:0] v);
        if (v > 18'sd32767)       sat16 = 16'sd32767;
        else if (v < -18'sd32768) sat16 = -16'sd32768;
        else                      sat16 = v[15:0];
    endfunction

    assign xr = sat16(sr[18:1]);
    assign xi = sat16(si[18:1]);
    assign yr = sat16(dr[18:1]);
    assign yi = sat16(di[18:1]);
endmodule
