Title: Here is an ~~example~~ of ==markdown== stuff
Date: 2019-05-13 22:02:44-07:00
Entry-ID: 162
UUID: d5311ad8-68b4-5a70-bf63-1eadfdb04ac4

We have ~~strikethrough~~ and ==highlight==

We have fenced code^5:

```c++
int main() {
    std::cout << "hello world" << std::endl;
    return 0;
}
```

We have a table:

| Animal | Noise   |
| ------ | ------- |
| cat    | meow    |
| dog    | woof    |
| platypus | mrah  |
| critter  | meep  |

Math?[^math] \\[
\begin{bmatrix}
foo & bar & baz \\\\
qwer & poiu & moo
\end{bmatrix}
\\]

[^math]: note that the `math` extension only affects the correctness of MathJax sections and doesn't itself enable MathJax
